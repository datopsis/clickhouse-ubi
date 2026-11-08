# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). GitHub Releases correspond only to published container images; repository-only changes remain under `Unreleased` until the next image release. See [docs/VERSION.md](docs/VERSION.md).

## [Unreleased]

### Added

- Restricted OpenShift qualification fixtures, policy tests, full operator procedure, and architecture diagram.
- Security-control/SCTM planning, FIPS and host-support boundaries, and a repository-native SVG architecture suite.
- Initial Red Hat UBI 9 Micro packaging for ClickHouse Server.
- Hardened non-root runtime, automated tests, vulnerability scanning, SBOM and provenance generation, and keyless release signing.
- Cross-platform line-ending rules and pre-commit checks for repository hygiene, shell scripts, container files, GitHub Actions, and prohibited commit trailers.
- Immutable GitHub Action references, workflow security auditing, configuration scanning, and expanded runtime smoke coverage.
- OpenSSF Scorecard publishing, CodeQL analysis for GitHub Actions, hash-locked CI tooling, CODEOWNERS, and signed GitHub release evidence.
- Syft SPDX SBOM generation and Grype vulnerability gates for CI and release images, with SARIF and release artifacts retained according to their useful lifecycle.
- First-release roadmap, repository badge policy, and contributor-facing CI and artifact documentation.
- A documented container and repository versioning and release standard.
- CI security-layer, enforcement, result-review, and Endor Labs guidance.
- Structured bug reporting and pull-request review checklists.
- Production, TLS, disconnected-deployment, vulnerability-triage, upstream-license, and official-image comparison documentation.
- Entrypoint initialization and health checks over TLS-only native-port configurations.
- Complete Grype JSON inventories, including unfixed findings, retained beside the fixed High/Critical blocking result in CI and release runs.
- Explicit ClickHouse TGZ component records in SPDX inventories and a keyless, digest-bound complete SPDX release attestation.
- Rootless storage guidance for named volumes, bind mounts, Kubernetes/OpenShift identities, custom data paths, additional disks, SELinux, and NFS.
- Native AMD64 and ARM64 CI builds, smoke tests, vulnerability evidence, and release-manifest architecture validation.
- Explicit repository scope and official-image storage compatibility guidance, including the XML-based replacement for the unreleased `CLICKHOUSE_DATA_DIR` interface.
- Podman-first user procedures, a tested Podman support baseline, and rootless user-namespace permission guidance.
- Native CA-issued TLS rehearsal covering HTTPS, native TCP, connected/disconnected outbound trust, negative cases, renewal, rollback, and operator evidence procedures.
- Dedicated loopback-only TLS health client configuration that supports CA-issued certificate chains without weakening server-side outbound verification.

### Security

- Refresh all UBI 9.8 Micro and Minimal base digests, including the OpenSCAP
  tool image, to pick up fixed PCRE2 and CA certificate packages on both native
  architectures. Rebuild the runtime RPM overlay against current UBI repositories.

### Changed

- Renamed the source repository and planned GHCR image from
  `clickhouse-server-ubi`/`clickhouse-server-ubi9` to `clickhouse-ubi`, aligning
  the public identity with the `nginx-ubi` and `postgresql-ubi` projects.
- The entrypoint now derives primary and additional writable directories from the effective ClickHouse configuration, rejects the misleading `CLICKHOUSE_DATA_DIR` variable, and reports non-root permission failures before server startup.
