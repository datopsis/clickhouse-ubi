# ClickHouse Server on Red Hat UBI 9

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/datopsis/clickhouse-ubi/badge)](https://securityscorecards.dev/viewer/?uri=github.com/datopsis/clickhouse-ubi)
[![CI](https://github.com/datopsis/clickhouse-ubi/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/datopsis/clickhouse-ubi/actions/workflows/ci.yml)
[![CodeQL](https://github.com/datopsis/clickhouse-ubi/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/datopsis/clickhouse-ubi/actions/workflows/codeql.yml)
[![Latest release](https://img.shields.io/github/v/release/datopsis/clickhouse-ubi?display_name=tag&sort=semver)](https://github.com/datopsis/clickhouse-ubi/releases)
[![License](https://img.shields.io/github/license/datopsis/clickhouse-ubi)](LICENSE)
[![Base: Red Hat UBI 9](https://img.shields.io/badge/base-Red%20Hat%20UBI%209-EE0000?logo=redhat&logoColor=white)](https://developers.redhat.com/products/rhel/ubi)
[![SBOM: SPDX JSON](https://img.shields.io/badge/SBOM-SPDX%20JSON-2F80ED)](docs/CI.md#artifacts-and-retention)

A minimal, security-oriented ClickHouse Server container image built on Red Hat Universal Base Image 9 Micro.

This is an independent Datopsis packaging project. It is not an official ClickHouse image and is not affiliated with or endorsed by ClickHouse, Inc. ClickHouse is a trademark of ClickHouse, Inc.

## Security properties

- Red Hat UBI 9 Micro runtime, pinned by multi-architecture digest
- Runtime RPM overlay pinned by exact NEVRA and SHA-256 for AMD64 and ARM64
- Official ClickHouse release archives, pinned by version and verified with the published SHA-512 checksums
- No package manager or package download utility in the runtime image
- Runs as the non-root `clickhouse` user (`101:0`)
- Compatible with a read-only root filesystem
- Requires no Linux capabilities for its baseline configuration
- Restricts the default user to localhost unless a password is supplied
- Native AMD64 and ARM64 CI smoke tests, repository linting, workflow auditing, and Trivy/Grype high and critical vulnerability admission under the [UBI-installable fix policy](SECURITY.md#ubi-installable-fix-gate)
- Syft-generated SPDX JSON inventories retained for CI builds and attached to releases
- Multi-architecture release images for `linux/amd64` and `linux/arm64`
- Keyless Cosign signatures, SBOM attestations, and build provenance on tagged releases

The builder uses UBI Minimal and is discarded. Only UBI Micro, a small set of UBI runtime packages, ClickHouse, and the entrypoint are present in the published image.

## Project scope

This repository owns the container artifact and its contract: build inputs, entrypoint behavior, ports, environment variables, configuration/mount conventions, rootless operation, primary Podman usage, Docker compatibility, image security evidence, and minimal platform-qualification fixtures.

Reusable production deployment topology belongs in the planned [clickhouse-production-stack](https://github.com/datopsis/clickhouse-production-stack) repository. That project should own deployable Compose/Kubernetes/OpenShift resources, clustering, ingress and network policy, secret integration, monitoring, backups, restore automation, and environment-specific sizing. Examples here remain intentionally small and exist to explain or test behavior specific to this image.

## Quick start

```console
podman run --detach \
  --name clickhouse \
  --publish 18123:8123 \
  --publish 19000:9000 \
  --ulimit nofile=262144:262144 \
  --env CLICKHOUSE_PASSWORD='replace-me' \
  --read-only \
  --tmpfs /tmp:size=256m,mode=1777 \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --volume clickhouse-data:/var/lib/clickhouse \
  ghcr.io/datopsis/clickhouse-ubi:<release-tag>
```

Then query it with a ClickHouse client:

```console
clickhouse-client --host 127.0.0.1 --port 19000 \
  --user default --password 'replace-me' \
  --query 'SELECT version()'
```

The included `compose.yaml` provides the same hardened local baseline. Change its example password before running `podman compose up --detach`. Podman's Compose command requires an installed Compose provider; see [Podman compatibility and version support](docs/PODMAN.md).

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `CLICKHOUSE_PASSWORD` | Password for the `default` user; enables network access | Empty; localhost only |
| `CLICKHOUSE_PASSWORD_FILE` | Read the default-user password from a mounted secret | Unset |
| `CLICKHOUSE_DB` | Create this database on the first start | Unset |
| `CLICKHOUSE_INIT_TIMEOUT` | Seconds to wait for the temporary initialization server | `60` |
| `CLICKHOUSE_ALWAYS_RUN_INITDB_SCRIPTS` | Run initialization scripts on every start when non-empty | Unset |
| `CLICKHOUSE_CONFIG` | Main server configuration file | `/etc/clickhouse-server/config.xml` |

The image intentionally manages only the built-in `default` user through environment variables. Create additional users with SQL or mounted ClickHouse configuration.

Mount configuration fragments under:

- `/etc/clickhouse-server/config.d/*.xml`
- `/etc/clickhouse-server/users.d/*.xml`

TLS is optional. The default profile exposes clear-text HTTP/native listeners;
the documented secure profile enables HTTPS/native TLS on `8443`/`9440` and
removes `8123`/`9000`. Select the mode with mounted ClickHouse configuration,
not an environment variable. See [TLS certificates and trust](docs/TLS.md).

Place first-start initialization files in `/docker-entrypoint-initdb.d`. Executable and sourced `.sh`, `.sql`, and `.sql.gz` files are supported and processed in lexical order.

The effective ClickHouse `<path>` setting controls persistent data and defaults to `/var/lib/clickhouse`. The entrypoint discovers configured primary and additional local paths, creates permitted subdirectories as the current identity, and fails with UID/GID guidance when storage is not writable. It never starts as root or changes volume ownership. See [rootless storage and permissions](docs/ROOTLESS.md) before using bind mounts, arbitrary UIDs, custom paths, or additional disks.

## Build and test

Install the pinned development checks and Git hooks once per clone:

```console
python -m pip install pre-commit==4.6.2
pre-commit install --install-hooks
pre-commit run --all-files
```

The hooks normalize text files to LF, reject common repository mistakes and private keys, lint shell scripts and the `Containerfile`, audit GitHub Actions syntax, and reject Claude co-author trailers in commit messages. The same checks run in CI. `.gitattributes` enforces LF in Git regardless of the contributor's operating system.

Podman is the primary documented local runtime. Podman uses OCI format by default, which does not preserve the `HEALTHCHECK` instruction, so local builds use Docker manifest format:

```console
podman build --format docker --file Containerfile \
  --tag ghcr.io/datopsis/clickhouse-ubi:test .
CONTAINER_RUNTIME=podman \
  IMAGE=ghcr.io/datopsis/clickhouse-ubi:test \
  bash tests/smoke.sh
```

Refresh runtime RPMs using the [RPM lock procedure](docs/RPM-LOCK.md). Base-image build arguments must match the committed lock; changing a base pin requires a lock refresh.

Build-time arguments are `CLICKHOUSE_VERSION`, `CLICKHOUSE_CHANNEL`, `UBI_MINIMAL_IMAGE`, and `UBI_MICRO_IMAGE`. Release builds should retain immutable UBI digests and an exact ClickHouse version.

The supported Podman baseline is version 5.3 or newer because 5.3.1 is the oldest engine on which the full smoke suite has been recorded. This is a tested support floor, not a claim that older versions cannot run the image. Docker Engine remains compatible and is used by GitHub Actions for its native architecture jobs and release Buildx workflow. See [Podman compatibility and version support](docs/PODMAN.md) for tested versions, rootless bind mounts, remote clients, and Compose behavior.

The smoke suite verifies startup with a read-only root filesystem and no capabilities, package-manager absence, authenticated local and network queries, first-start initialization, persistent-data restarts, password-file support, the passwordless network restriction, TLS-only native initialization and health, graceful shutdown, and operation under an arbitrary OpenShift-style UID. The separate CA-issued rehearsal validates chained certificates, HTTPS/native TLS, connected and disconnected outbound trust, negative cases, rotation, and rollback. Both require `openssl` on the test host; the TLS rehearsal also requires `curl`.

## Release process

1. Update and locally test the versions and digests in `Containerfile`.
2. Merge the change to `main` after CI passes.
3. Complete the release gates in [docs/ROADMAP.md](docs/ROADMAP.md).
4. Choose the next release version according to [docs/VERSION.md](docs/VERSION.md), validate it with `bash scripts/validate-release-tag.sh <tag>`, and create its tag, such as `v26.8.2.7-ubi9.8-1`.
5. Push the tag. GitHub Actions builds both architectures, scans the image with Trivy and Grype, publishes it to GHCR, attaches the complete SPDX SBOM and build provenance as attestations, signs the resulting digest, and creates a GitHub release containing the SPDX SBOM, Sigstore bundle, and in-toto evidence.

Verify a release with GitHub as the keyless identity provider:

```console
cosign verify \
  --certificate-identity-regexp='https://github.com/datopsis/clickhouse-ubi/.github/workflows/release.yml@refs/tags/.*' \
  --certificate-oidc-issuer='https://token.actions.githubusercontent.com' \
  ghcr.io/datopsis/clickhouse-ubi@sha256:<digest>

cosign verify-attestation --type spdxjson \
  --certificate-identity-regexp='https://github.com/datopsis/clickhouse-ubi/.github/workflows/release.yml@refs/tags/.*' \
  --certificate-oidc-issuer='https://token.actions.githubusercontent.com' \
  ghcr.io/datopsis/clickhouse-ubi@sha256:<digest>
```

## Operational notes

ClickHouse commonly benefits from `nofile=262144:262144`. Optional capabilities such as `IPC_LOCK`, `NET_ADMIN`, and `SYS_NICE` enable specific advanced behavior, but are deliberately absent from the baseline.

Treat the effective ClickHouse data path (default `/var/lib/clickhouse`) as durable state, back it up according to your ClickHouse topology, and pin production deployments to an image digest rather than a mutable tag.

Before a production rollout, follow the [production deployment guide](docs/PRODUCTION.md). Configure inbound encryption and public/private outbound trust with the [TLS guide](docs/TLS.md), then execute the [CA-issued TLS rehearsal](docs/TLS-REHEARSAL.md). OpenShift users should follow the [OpenShift qualification procedure](docs/OPENSHIFT-TESTING.md). The secure ClickHouse ports (`8443`, `9440`, and `9010`) are configuration choices and are not enabled by default.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and [first-release support boundaries](docs/SUPPORT.md) for qualified platforms and versions. Contributor references include [architecture diagrams](docs/ARCHITECTURE.md), [security-control and SCTM export](docs/SECURITY-CONTROLS.md), [FIPS determination](docs/FIPS.md), [Podman compatibility](docs/PODMAN.md), [rootless storage and permissions](docs/ROOTLESS.md), [qualification evidence](docs/QUALIFICATION.md), the [vulnerability-management process](docs/VULNERABILITY-MANAGEMENT.md), [official-image comparison](docs/IMAGE-COMPARISON.md), [versioning and release standard](docs/VERSION.md), [first-release roadmap](docs/ROADMAP.md), [CI and security process](docs/CI.md), [SCAP compliance scanning](docs/SCAP.md), [Endor Labs posture](docs/ENDOR.md), [badge policy](docs/BADGING.md), and [OpenSSF Scorecard controls](docs/OPENSSF_SCORECARD.md).

## License

The packaging code and documentation in this repository are licensed under Apache License 2.0. ClickHouse, Red Hat UBI, and their component packages remain subject to their respective upstream licenses and terms. See [third-party software and terms](THIRD_PARTY_NOTICES.md) for the distribution notices and release-review requirements.
