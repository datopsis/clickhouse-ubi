#!/usr/bin/env python3
"""Download verified locked RPMs, then install with every repository disabled."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from rpm_lock import ARCHITECTURES, identity, read, require, validate, verify_rpm  # noqa: E402


def install(lock, architecture, root):
    require(architecture in ARCHITECTURES, "unsupported target architecture")
    entries = lock["architectures"][architecture]
    with tempfile.TemporaryDirectory(prefix="locked-rpms-") as directory:
        paths = []
        for entry in entries:
            path = Path(directory) / identity(entry)[2]
            subprocess.run([
                "curl", "--fail", "--location", "--proto", "=https", "--proto-redir", "=https",
                "--tlsv1.2", "--retry", "5", "--retry-delay", "2", "--retry-all-errors",
                "--output", str(path), entry["url"],
            ], check=True)
            verify_rpm(path, entry)
            paths.append(str(path))
        # Import only the keys shipped by the digest-pinned UBI builder.
        root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rpm", "--root", str(root), "--import",
                        "/etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release"], check=True)
        subprocess.run([
            "dnf", "install", "-y", "--disablerepo=*", f"--installroot={root}",
            "--releasever=9", "--setopt=install_weak_deps=0", "--setopt=keepcache=0",
            "--setopt=localpkg_gpgcheck=1", *paths,
        ], check=True)
        installed = subprocess.check_output([
            "rpm", "--root", str(root), "-qa", "--qf",
            "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\n",
        ], text=True).splitlines()
        installed = sorted(p for p in installed if not p.startswith("gpg-pubkey-"))
        require(installed == sorted(e["nevra"] for e in entries), "installed RPM inventory differs from lock")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--architecture", choices=ARCHITECTURES, required=True)
    parser.add_argument("--builder-image", required=True)
    parser.add_argument("--runtime-image", required=True)
    args = parser.parse_args()
    lock = read(args.lock)
    validate(lock)
    require(lock["base_images"] == {"builder": args.builder_image, "runtime": args.runtime_image},
            "build argument base pins disagree with lock")
    # Every package inherited from Micro must also be supplied by the locked
    # full overlay, so a base refresh cannot silently introduce an unlisted RPM.
    inherited = subprocess.check_output([
        "rpm", "--dbpath", "/tmp/micro-rpm-db", "-qa", "--qf", "%{NAME}\n",
    ], text=True).splitlines()
    inherited = {name for name in inherited if name != "gpg-pubkey"}
    locked_names = {identity(e)[0] for e in lock["architectures"][args.architecture]}
    require(inherited and inherited <= locked_names, "Micro contains RPMs absent from lock")
    install(lock, args.architecture, Path("/runtime"))


if __name__ == "__main__":
    main()
