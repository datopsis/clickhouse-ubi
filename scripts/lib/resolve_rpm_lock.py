#!/usr/bin/env python3
"""Resolve and hash the complete empty-root overlay; never execute foreign RPMs."""

import argparse
import tempfile
from pathlib import Path

import dnf

from rpm_lock import ARCHITECTURES, REQUESTED, base_images, digest, render, validate, verify_rpm


def resolve(architecture):
    rpm_arch = ARCHITECTURES[architecture]
    with tempfile.TemporaryDirectory(prefix="rpm-resolver-") as directory, dnf.Base() as base:
        for name in ("root", "cache", "log", "persist"):
            Path(directory, name).mkdir()
        base.conf.read()
        base.conf.installroot = directory + "/root"
        base.conf.cachedir = directory + "/cache"
        base.conf.logdir = directory + "/log"
        base.conf.persistdir = directory + "/persist"
        base.conf.install_weak_deps = False
        base.conf.arch = rpm_arch
        base.conf.ignorearch = True
        base.conf.substitutions["arch"] = rpm_arch
        base.conf.substitutions["basearch"] = rpm_arch
        base.conf.substitutions["releasever"] = "9"
        base.conf.module_platform_id = "platform:el9"
        base.read_all_repos()
        base.fill_sack(load_system_repo=False)
        for name in REQUESTED:
            base.install(name)
        base.resolve()
        packages = sorted(base.transaction.install_set, key=lambda p: str(p))
        base.download_packages(packages)
        entries = []
        for package in packages:
            path = Path(package.localPkg())
            entry = {
                "nevra": f"{package.name}-{package.epoch}:{package.version}-{package.release}.{package.arch}",
                "url": package.remote_location(),
                "sha256": digest(path),
            }
            verify_rpm(path, entry)
            entries.append(entry)
        return sorted(entries, key=lambda e: e["nevra"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = {"schema_version": 1, "base_images": base_images(args.root),
            "requested": REQUESTED, "architectures": {}}
    for arch in ARCHITECTURES:
        lock["architectures"][arch] = resolve(arch)
        print(f"{arch}: {len(lock['architectures'][arch])} RPMs", flush=True)
    validate(lock)
    args.output.write_text(render(lock))


if __name__ == "__main__":
    main()
