#!/usr/bin/env python3
"""Read-only DNF query helper, run with the system Python and RPM bindings."""
import argparse
import json
import re
import sys
import tempfile

import dnf
import rpm

from lib.ubi_repos import RPM_ARCH, configure


def evr(value):
    # Vendor RPM fixes must include version AND release. Do not guess at ranges,
    # distro suffixes, missing versions, or semantic-version notation.
    if not isinstance(value, str):
        raise ValueError('RPM fixed version must be a string')
    match = re.fullmatch(r'(?:(\d+):)?([A-Za-z0-9][A-Za-z0-9._+~^]*)-([A-Za-z0-9][A-Za-z0-9._+~^]*)', value)
    if not match:
        raise ValueError(f'unparsable RPM EVR: {value!r}')
    epoch, version, release = match.groups()
    return epoch or '0', version, release


def at_least(candidate, fixed):
    return rpm.labelCompare(evr(candidate), evr(fixed)) >= 0


def query(base, request, arch):
    name, fixes = request['name'], request['fixes']
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+._-]*', name):
        raise ValueError('invalid RPM name')
    if not isinstance(fixes, list) or not fixes:
        raise ValueError('missing RPM fixed versions')
    for fixed in fixes:
        evr(fixed)
    packages = base.sack.query().available().filter(name=name, arch=[RPM_ARCH[arch], 'noarch'])
    candidates = sorted({f'{p.epoch}:{p.version}-{p.release}' for p in packages})
    # Any advertised fix branch that can be met must block. All supplied
    # versions are parsed first, so one malformed branch cannot be deferred.
    available = any(at_least(candidate, fixed) for candidate in candidates for fixed in fixes)
    return {'available': available, 'candidates': candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', required=True, choices=RPM_ARCH)
    args = parser.parse_args()
    requests = json.load(sys.stdin)
    if not isinstance(requests, list) or not requests:
        raise ValueError('missing query requests')
    with tempfile.TemporaryDirectory() as tmp, dnf.Base() as base:
        repos = configure(base, tmp, args.arch)
        results = []
        for request in requests:
            try:
                results.append(query(base, request, args.arch))
            except Exception as error:
                results.append({'error': str(error)})
    print(json.dumps({'repositories': repos, 'results': results}))


if __name__ == '__main__':
    main()
