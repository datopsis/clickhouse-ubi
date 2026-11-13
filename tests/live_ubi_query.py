"""Exercise positive and negative queries for every locked RPM on a native runner."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lib.rpm_lock import NEVRA, read

spec = importlib.util.spec_from_file_location('gate', ROOT / 'scripts/vulnerability-gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=['amd64', 'arm64'], required=True)
    args = parser.parse_args()
    entries = read(ROOT / 'artifacts/rpm-lock.json')['architectures'][args.arch]
    requests = []
    for entry in entries:
        name, epoch, version, release, _ = NEVRA.fullmatch(entry['nevra']).groups()
        requests.append({'name': name, 'fixes': [f'{epoch}:{version}-{release}']})
    positive = gate.repoquery(requests, args.arch)
    for result in positive['results']:
        if result.get('available') is not True or not result.get('candidates'):
            raise ValueError(f'locked RPM has no installable candidate: {result}')
    # A synthetic next epoch above every published candidate tests a successful
    # negative query without assuming any particular package will lack a fix.
    negatives = []
    for request, result in zip(requests, positive['results']):
        epoch = max(int(candidate.split(':', 1)[0]) for candidate in result['candidates']) + 1
        negatives.append({'name': request['name'], 'fixes': [f'{epoch}:1-1']})
    negative = gate.repoquery(negatives, args.arch)
    if any(result.get('available') is not False for result in negative['results']):
        raise ValueError('synthetic future-epoch query did not return unavailable')
    evidence = {'architecture': args.arch, 'positive_requests': requests,
                'positive': positive, 'negative_requests': negatives, 'negative': negative}
    Path('evidence').mkdir(exist_ok=True)
    Path('evidence/live-repoquery.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(f"{args.arch}: {len(requests)} positive and {len(negatives)} negative UBI queries passed")


if __name__ == '__main__':
    main()
