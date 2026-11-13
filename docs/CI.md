# Continuous integration and release automation

This repository treats the built image as the primary deliverable. CI therefore checks repository quality, builds and exercises the container, inventories its contents, and applies two independent vulnerability scanners before release. Required checks are deliberately few; each one groups related tools so branch protection stays understandable and runner use remains modest.

## Workflow map

| Workflow | Triggers | Purpose |
| --- | --- | --- |
| `CI` | Pull requests, pushes to `main`, six-hour schedule, manual dispatch | Lint and workflow audit, followed by native AMD64 and ARM64 image builds, smoke tests, isolated SCAP discovery, Trivy scans, Syft SBOMs, and Grype scans. |
| `CodeQL` | Workflow changes, weekly schedule, manual dispatch | Static analysis of GitHub Actions with the security-extended query suite. |
| `OpenSSF Scorecard` | Pushes to `main`, ruleset changes, weekly schedule, manual dispatch | Supply-chain posture analysis, SARIF upload, and public Scorecard publication. |
| `Release image` | Tags matching `v*` | Tag/input/changelog validation, multi-architecture publish, digest scans, evidence generation, keyless signing, and GitHub release creation. |

Workflow-level permissions default to read-only. Write scopes are applied only to jobs that publish code-scanning results, packages, attestations, signatures, releases, or the trusted-main deferred-fix tracking issue. Third-party actions are pinned to full commit SHAs and tracked by Dependabot.

## Analysis layers and why each exists

| Layer | Controls | What it can establish | Important limit |
| --- | --- | --- | --- |
| Repository hygiene | pre-commit built-ins and release-tag tests | Parseable YAML/JSON, normalized text, no obvious private keys, merge markers, unsafe symlinks, or oversized additions; release identifiers match image inputs and changelog state. | Pattern checks do not prove that no secret exists. GitHub secret scanning and push protection provide the native enforcement layer. |
| Source-specific lint | ShellCheck and Hadolint | Common shell defects and unsafe or wasteful container-build patterns. | These are static rules, not runtime evidence. |
| Workflow security | Actionlint, Zizmor, and CodeQL `actions` with `security-extended` | Workflow syntax, dangerous expressions, excessive permissions, untrusted checkout/data flows, artifact risks, and immutable references. | CodeQL runs on workflow changes and a schedule; Zizmor runs in every `lint` job. |
| Build configuration | Trivy configuration scan | High/critical Containerfile and infrastructure misconfigurations. | A clean configuration scan says nothing about packages in the built image. |
| Runtime behavior | Native GitHub-hosted AMD64 and ARM64 runners, Buildx, and `tests/smoke.sh` | Each architecture's exact test image starts and stops correctly under production-oriented restrictions and supports documented initialization/authentication behavior. Runner and loaded-image assertions prevent emulation or a mislabeled image from being treated as native evidence. | Hosted-runner tests do not replace OpenShift qualification or application-specific performance testing. |
| Image vulnerabilities | Trivy image scan | High/critical admission follows the [UBI-installable fix policy](../SECURITY.md#ubi-installable-fix-gate). | Deferred and unfixed findings remain visible and require human release review. |
| Independent inventory and scan | Syft plus Grype | SPDX inventory of the tested image and a second vulnerability matcher/database; the same admission policy applies to fixed high/critical findings. | Overlap is intentional, but scanner agreement is not proof of absence. |
| Filesystem compliance | Pinned OpenSCAP engine, ComplianceAsCode RHEL 9 content, and reviewed Datopsis tailoring | Architecture-specific results for 36 image-owned rules against a root-owner-preserving export; scanner errors block. | Selected-rule findings remain non-blocking during stabilization. This is neither wholesale STIG adoption nor host/deployment certification. |
| Supply-chain posture | OpenSSF Scorecard | Repository and build-pipeline practice signals published independently. | Historical and popularity signals improve only through genuine project operation. |
| Release integrity | BuildKit attestations, Cosign, GHCR, and GitHub Releases | Digest-bound multi-architecture artifact, SBOM/provenance evidence, keyless signature, and durable release assets. | The tag workflow publishes before post-build scans; a failed candidate must be quarantined or removed. |

No additional general-purpose scanner is currently justified. Dependency Review has little useful input without a supported package manifest; another image CVE scanner would duplicate Trivy and Grype; another secret action would duplicate GitHub secret scanning and the private-key hook; and a generic SAST action would add little beyond ShellCheck, CodeQL Actions, and Zizmor for this shell/container repository. Reconsider when the repository gains a new language, manifest, deployment format, or credible fuzz target. See [ENDOR.md](ENDOR.md) for the conditional Endor Labs adoption decision.

## Pull request and merge process

1. A pull request starts the two protected checks: `lint` and the aggregate `image` check. The aggregate succeeds only after both `image (amd64)` and `image (arm64)` succeed. Workflow-file changes also start CodeQL.
2. Reviewers inspect both architecture jobs, the diff, annotations, scanner summaries, smoke-test versions, and the retained architecture-specific SBOM/SARIF artifacts. They confirm skipped steps are expected for the event and review warnings or ignored findings.
3. The active `main` ruleset requires a pull request, resolved review threads, and the latest `lint` and `image` results before merge; it also blocks deletion and force pushes. Required approving reviews remain deliberately disabled until the post-first-release review described in [ROADMAP.md](ROADMAP.md).
4. A merge starts `CI` on the exact `main` commit. Workflow changes start CodeQL, and every main push refreshes Scorecard. These post-merge runs are reviewed because merge-commit context, secrets, permissions, and SARIF publication differ from pull requests.
5. Six-hour CI refreshes vulnerability evidence and deferred-fix tracking; weekly schedules refresh other workflow analysis even when source has not changed. Manual dispatch supports investigation; it is not a substitute for the pull-request checks.
6. Only a validated annotated container-version tag starts a release. The workflow verifies that the tag's ClickHouse and UBI versions match `Containerfile` and that the changelog has a dated matching section before publishing.

Concurrency cancels superseded CI, CodeQL, and Scorecard work for the same ref. Releases are never automatically cancelled. Job timeouts bound stuck or compromised work without hiding a failed control.

## Enforced GitHub settings

Repository configuration is part of the security boundary, even though it is not stored in Git:

- Actions are enabled, the default `GITHUB_TOKEN` permission is read-only, and workflows cannot approve pull requests.
- GitHub requires third-party Actions to be referenced by a full commit SHA. Workflow files also keep the release tag in a comment for review and Dependabot updates.
- The `Protect main` ruleset requires pull requests, resolved review threads, and successful, up-to-date `lint` and aggregate `image` checks; it prevents branch deletion and non-fast-forward updates. The aggregate preserves the stable protected-check name while requiring both native architecture jobs. The required approval count is intentionally zero for now.
- Secret scanning, push protection, Dependabot security updates, and private vulnerability reporting are enabled.
- Workflow permissions are narrowed per job; only code-scanning publication, OIDC signing, package publication, release creation, and trusted-main deferred-fix tracking receive write scopes.

Audit these settings before each release and after organization policy changes. A file review cannot detect a disabled ruleset or broadened repository-level token policy.

## Reviewing a result rather than a color

For every required run, verify the event and head SHA first. Then review the following evidence:

- `lint`: every hook and the release-tag test ran, Zizmor audited every workflow, and there are no warnings or annotations hidden behind a successful wrapper.
- `image (amd64)` and `image (arm64)`: the native runner assertion, loaded-image architecture assertion, configuration scan count, ClickHouse version printed by the smoke suite, SCAP execution outcome and result counts, Trivy target/OS/package count and result count, SBOM package count, and Grype's fixed-findings SARIF, both full scanner inventories, and the gate's blocking/deferred/unfixed decisions. The aggregate `image` job is only the merge gate; inspect the two jobs that produced the evidence.
- `CodeQL` and Scorecard: analysis covered the intended files, SARIF processing completed, and the Security tab has no new open alert. A successful upload is not the same as zero findings.
- skipped steps: PR SARIF publication is intentionally skipped to avoid permission failures from untrusted forks; it runs on `main`. Tracking issue writes run only on scheduled/manual `main` runs. A skipped build, smoke test, or scanner is not acceptable.
- warnings: Trivy may use another vendor's severity when Red Hat data is absent. Grype's `only-fixed` option can ignore real but currently unfixable findings. Review both against Red Hat and ClickHouse advisories before a release.

Record accepted findings in the release pull request with the advisory, affected package, architecture, fix availability, rationale, owner, compensating control, and expiry. Do not rerun until a transient failure turns green or treat an empty SARIF file as proof that the scanner evaluated every risk category.

## Image security pipeline

Each native image matrix job runs these controls in order. AMD64 uses `ubuntu-24.04` and `linux/amd64`; ARM64 uses `ubuntu-24.04-arm` and `linux/arm64`. QEMU is not installed and does not count as native-runtime evidence.

1. **Trivy configuration scan** checks the `Containerfile`, Compose configuration, and repository infrastructure configuration for high and critical misconfigurations.
2. **Build and runtime tests** exercise startup, authentication, initialization, persistence, shutdown, read-only operation, dropped capabilities, arbitrary UIDs, chained CA-issued HTTPS/native TLS, public/private outbound trust, disconnected isolation, negative certificate cases, renewal, and rollback.
3. **Tailored OpenSCAP evaluation** builds a pinned-input UBI scanner, exports but never executes the stopped target, preserves filesystem ownership inside an isolated tmpfs, and evaluates 36 explicitly selected image-owned rules without network or an engine socket. The initial full RHEL 9 STIG discovery and every selection/exclusion decision are recorded in [SCAP.md](SCAP.md) and the [rule rationale](../security/scap/RULE-RATIONALE.md). Findings remain report-only during stabilization; execution errors block.
4. **Trivy image scan** retains all severities, unfixed vulnerabilities, and secret findings as JSON for the mandatory gate and reports its detected OS and package count for review.
5. **Complete SPDX inventory** uses Syft to inventory the tested filesystem and RPM database, then `scripts/augment-spdx.py` declares the three pinned ClickHouse TGZ components that have no RPM metadata. The script takes their version and channel from `Containerfile`, records Apache-2.0 licensing and package identifiers, and fails instead of duplicating a component Syft already found.
6. **Grype SBOM scan** scans that exact SPDX document and retains fixed high and critical findings as SARIF. Admission decisions come from the complete JSON and shared gate.
7. **Full Grype inventory** performs a non-blocking scan of the same SBOM without filtering unfixed matches and retains `grype-all.json`. Non-blocking means “record for triage,” not “accepted risk.”
8. **Mandatory admission gate** blocks fixable High/Critical non-RPM findings and RPM fixes available from the pinned builder's repositories. Successful negative RPM queries defer with vendor fixed versions; errors fail closed. High/Critical Trivy secrets still block. Native live queries verify both available and unavailable outcomes.
9. **Artifact and SARIF publication** retains the inventory and results for investigation and publishes fixed Grype findings from non-PR runs to GitHub code scanning.

Trivy and Grype deliberately overlap. They use different databases and matching logic, so a clean result from one does not replace the other. Unfixed findings do not block admission, but remain in complete reports and require periodic review before release. Deferred RPM findings also remain visible with vendor fixed versions. Scanner disagreements should be investigated against the vendor advisory and documented if accepted.

## Artifacts and retention

| Artifact | Location | Retention or lifecycle | Purpose |
| --- | --- | --- | --- |
| `clickhouse-ubi-<architecture>.spdx.json` | CI artifact `image-security-<commit>-<architecture>` | 14 days | Package inventory for the exact native AMD64 or ARM64 test image. |
| `grype-<architecture>.sarif` | Same architecture-specific CI artifact and GitHub code scanning on non-PR runs | 14 days for the downloadable artifact | Machine-readable findings and architecture-specific review evidence. |
| `grype-all-<architecture>.json` | Architecture-specific CI artifact | 14 days | Complete point-in-time inventory including unfixed Low and Medium matches for human triage. Release artifacts retain the same architecture-specific filenames for 30 days. |
| `trivy-all-<architecture>.json` and `evidence/` | Architecture-specific CI/release artifact | 14 days in CI; 30 days for releases | Complete Trivy findings, gate decisions, vendor fix versions, repository URLs/hashes and query candidates. |
| `scap-results-<architecture>/` | Architecture-specific CI artifact | 14 days | Tailored ARF/XCCDF/HTML, full JSON rule inventory, exit code, data-stream and tailoring hashes, scanner version, and RPM versions for the exact target/scanner image IDs. |
| `image.spdx.json` | GitHub release asset (copied from the admitted AMD64 SPDX artifact) | 30-day Actions copy; release asset retained with the release | Downloadable inventory for the published digest. |
| Release `grype-<architecture>.sarif` | Tag-run artifact and GitHub code scanning | 30 days for the downloadable artifact | Point-in-time scan evidence; not attached to the release because vulnerability data ages rapidly. |
| BuildKit SBOM/provenance and complete SPDX attestation | OCI registry attestations; downloaded together as `image.intoto.jsonl` | Lifetime of the package/release | Registry-native build evidence plus the keyless, digest-bound copy of `image.spdx.json`. |
| `image.sigstore.json` | GitHub release asset | Lifetime of the release | Offline verification bundle for the keyless image signature. |
| Scorecard SARIF | Scorecard workflow artifact and code scanning | 5 days for the workflow artifact | Supply-chain control findings. |

Upload steps use `always()` so useful evidence survives a vulnerability gate failure. A failed gate still prevents signing and release creation. Never place credentials, mounted secrets, or environment dumps in an uploaded artifact.

## Reproducing checks locally

Run the repository checks and build on a native Linux host. Set the expected values to `amd64`/`x86_64` on an AMD64 host or `arm64`/`aarch64` on an ARM64 host:

```console
pre-commit run --all-files --show-diff-on-failure
ARCHITECTURE=amd64
MACHINE=x86_64
test "$(uname -m)" = "${MACHINE}"
podman build --format docker --platform "linux/${ARCHITECTURE}" \
  --file Containerfile --tag "clickhouse-ubi:test-${ARCHITECTURE}" .
test "$(podman image inspect --format '{{.Architecture}}' \
  "clickhouse-ubi:test-${ARCHITECTURE}")" = "${ARCHITECTURE}"
CONTAINER_RUNTIME=podman \
  IMAGE="clickhouse-ubi:test-${ARCHITECTURE}" bash tests/smoke.sh
```

Build and run the isolated tailored SCAP scanner with the Podman procedure in
[SCAP.md](SCAP.md). It intentionally creates a second tooling image and does
not alter the ClickHouse deliverable.

Running an ARM64 image under emulation on an AMD64 workstation can help diagnose portable build failures, but it does not reproduce the native ARM64 qualification. GitHub's `ubuntu-24.04-arm` runner supplies that evidence using Docker Engine and Buildx. To reproduce both jobs faithfully, run the procedure once on each native architecture and retain separate results. Podman and Docker exercise the same image contract but remain distinct runtime implementations, so first-release evidence records both the native CI results and the separately tested Podman version.

For the scanner examples below, keep using the architecture-specific image name:

```console
ARCHITECTURE=amd64
IMAGE="clickhouse-ubi:test-${ARCHITECTURE}"
```

With Trivy, Syft 1.51.1, and Grype 0.118.0 installed from their official release instructions:

```console
trivy config --severity HIGH,CRITICAL --exit-code 1 .
trivy image --scanners vuln,secret --format json --exit-code 0 \
  --output "trivy-all-${ARCHITECTURE}.json" "${IMAGE}"
syft "${IMAGE}" --output "spdx-json=clickhouse-ubi-${ARCHITECTURE}.spdx.json"
python scripts/augment-spdx.py \
  --input "clickhouse-ubi-${ARCHITECTURE}.spdx.json" \
  --output "clickhouse-ubi-${ARCHITECTURE}.spdx.json"
grype "sbom:clickhouse-ubi-${ARCHITECTURE}.spdx.json" \
  --only-fixed --output sarif > "grype-${ARCHITECTURE}.sarif"
grype "sbom:clickhouse-ubi-${ARCHITECTURE}.spdx.json" \
  --output json > "grype-all-${ARCHITECTURE}.json"
CONTAINER_RUNTIME=podman python3 scripts/vulnerability-gate.py \
  --arch "${ARCHITECTURE}" "trivy-all-${ARCHITECTURE}.json" "grype-all-${ARCHITECTURE}.json"
```

The final command enforces admission and writes `evidence/vulnerabilities.json`; inspect the reports and the status. Vulnerability databases are time-dependent, so a local result can differ from an earlier workflow. Record the database update time and scanner version when investigating a discrepancy. Do not commit generated SBOM, SARIF, or full-scan JSON files; CI and releases are their authoritative storage locations.

## Contributor expectations

- Run pre-commit and the smoke suite before opening a pull request that affects the image or entrypoint.
- Inspect annotations and downloadable SARIF instead of rerunning a failed job until it happens to pass.
- For a true positive, update the affected base image, package, or ClickHouse version and rerun both scanners.
- For a suspected false positive, verify the package version and Red Hat/ClickHouse advisory, then open a narrowly scoped issue. The gate has no local vulnerability, package, or date exemptions.
- Update the explicit Syft and Grype engine versions together with their action references when reviewing dependency updates.
- Never merge a scanner bypass solely to meet a release date.

## Release behavior

The release workflow builds and pushes a multi-architecture manifest before scanners run because both architectures must be addressed by the immutable registry digest. It immediately inspects that digest and fails unless Linux AMD64 and ARM64 descriptors are both present. If manifest validation or a post-push scan fails, the workflow does not sign or create a GitHub release, but the registry may contain the non-release tag and digest. Maintainers must investigate and remove or clearly quarantine such failed candidates through the GHCR interface.

After Trivy, Grype, and admission pass on both native architectures, the workflow publishes the complete SPDX document as a keyless, digest-bound `spdxjson` attestation and signs the digest through GitHub OIDC. It then downloads all attestations and creates a GitHub release containing the SPDX SBOM, Sigstore bundle, and in-toto evidence. Follow the final checklist in [ROADMAP.md](ROADMAP.md) for the first release.

Authoritative references:

- [Anchore SBOM Action](https://github.com/anchore/sbom-action)
- [Anchore Scan Action](https://github.com/anchore/scan-action)
- [Syft documentation](https://github.com/anchore/syft/wiki)
- [Grype documentation](https://github.com/anchore/grype)
- [Trivy documentation](https://trivy.dev/latest/docs/)
- [GitHub artifact storage](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)
- [Uploading SARIF to GitHub](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/uploading-a-sarif-file-to-github)
- [GitHub-hosted runners, including Arm64 labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [BuildKit attestations](https://docs.docker.com/build/metadata/attestations/)
- [Cosign container signing](https://docs.sigstore.dev/cosign/signing/signing_with_containers/)
