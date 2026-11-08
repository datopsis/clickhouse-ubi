#!/usr/bin/env python3
"""Validate the RPM lock and the runtime/scanner base image pins."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
from rpm_lock import check_bases, read, render, require, validate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "artifacts/rpm-lock.json")
    args = parser.parse_args()
    try:
        lock = read(args.lock)
        validate(lock)
        check_bases(lock, ROOT)
        require(args.lock.read_text() == render(lock), "lock is not canonically formatted")
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"RPM lock rejected: {error}", file=sys.stderr)
        return 1
    for arch, entries in lock["architectures"].items():
        print(f"{arch}: {len(entries)} locked RPMs; base pins agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
