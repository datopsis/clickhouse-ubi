"""Shared, standard-library-only runtime RPM lock validation."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ARCHITECTURES = {"amd64": "x86_64", "arm64": "aarch64"}
REQUESTED = ["bash", "ca-certificates", "coreutils-single", "gzip", "tzdata"]
NEVRA = re.compile(r"([a-zA-Z0-9_+.-]+)-([0-9]+):([a-zA-Z0-9_+.~^]+)-([a-zA-Z0-9_+.~^]+)\.(x86_64|aarch64|noarch)")
BASES = {"builder": "UBI_MINIMAL_IMAGE", "runtime": "UBI_MICRO_IMAGE"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object)


def render(lock):
    return json.dumps(lock, indent=2, sort_keys=True) + "\n"


def base_images(root):
    text = (Path(root) / "Containerfile").read_text()
    result = {}
    for role, arg in BASES.items():
        matches = re.findall(rf'^ARG {arg}="([^"]+)"$', text, re.MULTILINE)
        require(len(matches) == 1, f"expected one pinned {arg}")
        result[role] = matches[0]
    return result


def identity(entry):
    match = NEVRA.fullmatch(entry["nevra"])
    require(match is not None, f"invalid NEVRA: {entry['nevra']}")
    name, epoch, version, release, arch = match.groups()
    require(str(int(epoch)) == epoch, "epoch must be canonical")
    return name, arch, f"{name}-{version}-{release}.{arch}.rpm"


def validate(lock):
    require(set(lock) == {"schema_version", "base_images", "requested", "architectures"}, "unexpected lock fields")
    require(type(lock["schema_version"]) is int and lock["schema_version"] == 1, "unsupported schema_version")
    require(set(lock["base_images"]) == set(BASES), "missing base image pins")
    for role, image in lock["base_images"].items():
        variant = "minimal" if role == "builder" else "micro"
        require(isinstance(image, str) and re.fullmatch(
            rf"registry\.access\.redhat\.com/ubi9/ubi-{variant}:9\.[0-9]+@sha256:[0-9a-f]{{64}}", image
        ), f"invalid {role} base pin")
    require(lock["requested"] == REQUESTED, "runtime package request changed or missing")
    require(set(lock["architectures"]) == set(ARCHITECTURES), "both amd64 and arm64 are required")
    names_by_arch = []
    for arch, rpm_arch in ARCHITECTURES.items():
        entries = lock["architectures"][arch]
        require(isinstance(entries, list) and entries, f"{arch}: empty RPM lock")
        names = set()
        for entry in entries:
            require(set(entry) == {"nevra", "url", "sha256"}, f"{arch}: invalid RPM fields")
            require(all(isinstance(v, str) for v in entry.values()), "RPM fields must be strings")
            name, package_arch, filename = identity(entry)
            require(package_arch in (rpm_arch, "noarch"), f"{arch}: wrong RPM architecture")
            require(name not in names, f"{arch}: duplicate package {name}")
            names.add(name)
            require(re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), f"{arch}: invalid SHA-256")
            url = urlsplit(entry["url"])
            prefix = f"/content/public/ubi/dist/ubi9/9/{rpm_arch}/"
            require(url.scheme == "https" and url.netloc == "cdn-ubi.redhat.com"
                    and not url.query and not url.fragment
                    and re.fullmatch(re.escape(prefix) + r"(baseos|appstream|codeready-builder)/os/Packages/[a-z0-9]/" + re.escape(filename), url.path),
                    f"{arch}: invalid repository URL for {entry['nevra']}")
        require(set(REQUESTED) <= names, f"{arch}: missing requested RPM")
        require(entries == sorted(entries, key=lambda e: e["nevra"]), f"{arch}: RPMs must be sorted")
        names_by_arch.append(names)
    require(names_by_arch[0] == names_by_arch[1], "architectures have different package sets")


def check_bases(lock, root):
    require(lock["base_images"] == base_images(root), "Containerfile base pins disagree with lock")
    scap = (Path(root) / "Containerfile.scap").read_text()
    matches = re.findall(r'^ARG UBI_MINIMAL_IMAGE="([^"]+)"$', scap, re.MULTILINE)
    require(matches == [lock["base_images"]["builder"]], "Containerfile.scap base pin disagrees with lock")


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def verify_rpm(path, entry):
    # Check bytes before even asking rpm to parse an untrusted header.
    require(digest(path) == entry["sha256"], f"SHA-256 mismatch: {entry['nevra']}")
    import subprocess
    actual = subprocess.check_output([
        "rpm", "-qp", "--qf", "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}", str(path)
    ], text=True)
    require(actual == entry["nevra"], f"NEVRA mismatch: expected {entry['nevra']}, got {actual}")
