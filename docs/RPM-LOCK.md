# Runtime RPM lock

`artifacts/rpm-lock.json` records the UBI Minimal and Micro multi-architecture
base digests and every RPM in the runtime overlay, separately for `amd64` and
`arm64`. Each entry includes its exact NEVRA (including epoch), Red Hat repository
URL, and SHA-256. The five requested runtime packages and their complete strong
dependency closure are resolved into an empty root, as in the original build.
The base image content is pinned by digest; the overlay supplies the runtime RPM
inventory. The build also requires every inherited Micro package name to be
present in the overlay lock. Builder-only tools are discarded and are outside this runtime lock.

Ordinary builds validate the lock and the effective base build arguments,
download only the named RPM URLs, and verify every digest and RPM header before
installation. DNF installs local files with **all repositories disabled**, weak
dependencies disabled, and RPM signature checking enabled using the pinned UBI
builder's Red Hat keys. Missing dependencies fail the transaction; the installed
NEVRA inventory must then exactly equal the lock. No package manager or lock
refresh tool is copied into the final image. ClickHouse TGZ version selection
and SHA-512 verification are unchanged.

## Refresh

Requirements: Python 3 and Podman (or Docker). Run from the repository root:

```console
# If refreshing UBI, first edit both Containerfile and Containerfile.scap pins.
bash scripts/update-rpm-lock.sh /tmp/rpm-lock-first.json
bash scripts/update-rpm-lock.sh /tmp/rpm-lock-second.json
cmp /tmp/rpm-lock-first.json /tmp/rpm-lock-second.json
cp /tmp/rpm-lock-second.json artifacts/rpm-lock.json
python3 .github/scripts/check_artifact_lock.py
git diff -- artifacts/rpm-lock.json
pre-commit run --all-files
python3 -m unittest discover --start-directory tests --pattern 'test_*.py'
```

Set `CONTAINER_RUNTIME=docker` to use Docker. The resolver's `FROM` explicitly
selects the **host** platform. DNF resolves each target architecture using its
own `arch` and `basearch` substitutions, with an empty RPM database; foreign RPMs
are only downloaded and queried, never installed or executed. This works without
QEMU. The generator writes only after both architectures resolve and validate.

Output contains no timestamps, host paths, or human sign-offs. Sorted packages
and canonical JSON give byte-identical locks for identical resolution inputs.
Red Hat repository metadata is a refresh input and can change between runs;
if two runs differ, inspect the changes and repeat against stable inputs.
Ordinary builds never consult that metadata. A removed locked URL fails the
build; it does not fall back to a newer version. Refresh the lock explicitly.

`Update RPM lock` runs on relevant pull requests and manual dispatch. It resolves
both architectures twice with the pinned UBI resolver, compares the outputs,
validates the proposal against both Containerfiles, and uploads the proposed
lock plus `rpm-lock.patch`. The workflow has only `contents: read`: it never
commits, approves changes, or opens pull requests. Download and inspect its
artifact, commit the selected lock, then require the usual native AMD64/ARM64
smoke, TLS, SCAP, Trivy, and Grype results. Scan policies and release signing
remain unchanged.

The regular CI lint job and local pre-commit hook reject malformed locks,
missing/duplicate packages, wrong architectures, non-Red-Hat URLs, invalid
checksums, unexpected fields, and base-pin drift. The build additionally checks
actual bytes, package headers, dependencies, and installed inventory.

## Design

This uses the single-file lock and read-only update proposal pattern from
[lakekeeper-ubi](https://github.com/datopsis/lakekeeper-ubi/blob/main/scripts/update-rpm-lock.sh),
including its explicit native resolver platform. Unlike that image, this repo
already installs a full empty-root overlay, so no Micro database delta or
reinstall special cases are needed. The explicit NEVRA fields follow the useful
identity convention in
[nginx-ubi](https://github.com/datopsis/nginx-ubi/blob/main/artifacts/locks/amd64.json).
NGINX's separate source-RPM inventories, signing-key acquisition pipeline, and
per-architecture bundle files would add unnecessary machinery here. All scripts
and data used by builds live in this repository; neither sibling is a dependency.
