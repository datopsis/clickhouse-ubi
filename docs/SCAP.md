# SCAP compliance scanning

SCAP is useful as a configuration-compliance control for this image, but an
unmodified RHEL host profile is not an appropriate release gate for a minimal
container. Many RHEL rules govern the kernel, boot loader, partitions, systemd,
audit daemon, host networking, or machine-wide security policy. Those controls
belong to the container host or deployment platform and are outside this
image's control.

The project therefore established a measured discovery baseline and now
maintains a tailored UBI 9 Micro container profile containing only applicable,
image-owned rules. Passing that profile means the inspected image filesystem
meets the documented rules; it is not a claim that the image, host, OpenShift
cluster, or complete ClickHouse deployment is CIS- or STIG-certified.

## Pinned scanner and content

The discovery implementation pins these inputs. An update requires changing
the values in `Containerfile.scap`, recalculating both hashes, reviewing the
content changes, and rerunning both native architecture jobs.

| Input | Pin | Verification |
| --- | --- | --- |
| Scanner base | UBI Minimal 9.8 manifest digest `sha256:4b79c93106c14ad1c234907f83441ff0e4f8d24e78426a36e159098e9f7e6fa5` | BuildKit resolves the digest for the native runner architecture. |
| OpenSCAP engine | UBI AppStream RPM `openscap-scanner-1.3.14-1.el9_8` | The build fails if that exact NEVRA cannot be installed; the complete resulting RPM inventory and `oscap --version` are retained so dependency drift is visible. |
| ComplianceAsCode content | Release `0.1.82` ZIP | Archive SHA-256 `765e84bdce7f9055f9b9c2dd0ee2b713d4255f8eec94eac6d35ea4973c28919c` is checked before extraction. |
| RHEL 9 data stream | `ssg-rhel9-ds.xml` from release `0.1.82` | Data-stream SHA-256 `92204daafbf4f38011671ef034fae4cffb48f708516186710346a9ec702a1f8f` is checked at build and recorded at evaluation. |
| Discovery profile | `xccdf_org.ssgproject.content_profile_stig` | Used for the initial broad inventory only. ComplianceAsCode 0.1.82 does not contain a RHEL 9 Standard profile. |
| Tailored profile | `xccdf_org.datopsis_profile_ubi9_micro_container` | Explicitly selects 36 image-owned rules and inherits no upstream profile. Its SHA-256 is recorded for every evaluation. |

Red Hat's public UBI 9 AppStream repositories provide `openscap-scanner` for
both x86_64 and aarch64, but do not provide `openscap-utils`. Consequently,
the implementation invokes the documented `OSCAP_PROBE_ROOT` offline mode
directly instead of relying on the `oscap-chroot` convenience wrapper from
`openscap-utils`. The underlying OpenSCAP offline evaluation mechanism is the
same. CI records the locally built scanner image ID; if the project later
publishes the tool image for reuse, consumers must use its manifest digest,
not its mutable tag.

`Containerfile.scap` and the scanner scripts are CI tooling only. They do not
add OpenSCAP, Python, `unzip`, a package manager, or any scanner content to the
released ClickHouse image. The scanner image defaults to unprivileged UID/GID
65534; only the reviewed wrapper overrides it to namespaced UID 0 while adding
the explicitly bounded mounts, capabilities, network isolation, and limits.

## CI security architecture

Do not run Podman inside Podman and do not mount a Docker or Podman socket into
the scanner. Nested container engines commonly require additional namespace,
device, seccomp, and capability allowances. A mounted engine socket also gives
the job control over the host engine. Either design makes the scanner a larger
privileged attack surface than the artifact being inspected warrants.

Use this flow instead:

1. Build and smoke-test the architecture-specific image in the existing native
   CI job.
2. Create a stopped container and export its merged filesystem to an ephemeral
   tar archive. `create` and `export` do not execute image content.
3. Run the locally built, pinned-input UBI 9 OpenSCAP tool image with that tar
   archive mounted read-only and a separate results directory mounted
   read-write. Extract inside the scanner's disposable tmpfs as namespaced UID
   0 so numeric owners and modes are preserved; unprivileged host extraction
   would corrupt ownership evidence.
4. Evaluate the extracted tree with `OSCAP_PROBE_ROOT` and the pinned RHEL 9
   data stream. Give the scanner no engine socket, host namespace, workflow
   secret, or evaluation-time network. Drop all capabilities, then add only
   `CAP_CHOWN` and `CAP_FOWNER` to preserve exported metadata,
   `CAP_DAC_OVERRIDE` to read restrictive target files and write the
   host-owned results mount, and `CAP_SYS_CHROOT` for offline probes. Enable
   `no-new-privileges`, make the scanner root filesystem read-only, and bound
   memory and process count. Limit writable storage to the extracted-root and
   OpenSCAP temporary tmpfs mounts plus the results directory.
5. Upload the ARF XML, XCCDF results, HTML report, tool/content versions, data
   stream hash, image digest, architecture, and tailoring hash as CI evidence.
6. Delete the exported root filesystem and stopped container after the job.

The scanner process runs as UID 0 *inside its isolated scanner container* so
it can inspect the mounted tree. That is different from granting the workflow a
privileged container, host root, an engine socket, or broad host mounts. The
target filesystem remains read-only and the ClickHouse image is never started
as root.

The native CI jobs prove that the scan operates with only those four named
capabilities after `--cap-drop all`. If either runner cannot operate with that
narrow allowance, the job fails; do not add `--privileged` or broader
capabilities to make it pass.

The scanner build and evaluation steps temporarily continue so later security
checks and artifact upload still run. A final step requires both outcomes to
be successful, so this sequencing preserves evidence without weakening the
required `image` check.

## Result semantics and evidence

During stabilization, findings are non-blocking only for ordinary `fail`, `notapplicable`, and
`notchecked` rule results. Failure to build or run the scanner, malformed or
empty XCCDF, and any `error`, `unknown`, or missing result fail the architecture
job. This distinction prevents "report-only" from hiding a broken scan.

Each `image-security-<commit>-<architecture>` artifact includes:

- `results.arf.xml`, the complete Asset Reporting Format evidence;
- `results.xccdf.xml`, the machine-readable evaluation results;
- `report.html`, the reviewer-oriented report;
- `summary.json`, a deterministic count and complete rule/result inventory;
- `tailoring.sha256`, binding the evaluation to the reviewed profile;
- the OpenSCAP version, exact installed RPMs, data-stream hash, and OpenSCAP
  exit code.

`summary.json` also binds the evidence to the target image ID, scanner image
ID, architecture, profile, data-stream SHA-256, and tailoring SHA-256. The
wrapper independently compares the scanner's tailoring hash with the
repository file and requires the actually evaluated rule IDs to equal all 36
explicit selections. This catches a stale scanner copy, a misspelled selector,
or silent profile expansion even if OpenSCAP returns a successful exit status.
The summary deliberately does not
label an upstream discovery-profile result as container, host, CIS, or STIG
certification.

## Initial native discovery result

[GitHub Actions run 34151979084](https://github.com/datopsis/clickhouse-ubi/actions/runs/34151979084)
qualified commit `c099690` on both native architectures. The retained AMD64
and ARM64 inventories contained the same 1,540 rule IDs and results:

| Result | AMD64 | ARM64 |
| --- | ---: | ---: |
| `pass` | 59 | 59 |
| `fail` | 7 | 7 |
| `notapplicable` | 410 | 410 |
| `notchecked` | 1 | 1 |
| `notselected` | 1,063 | 1,063 |
| `error`, `unknown`, or missing | 0 | 0 |

OpenSCAP returned its documented noncompliance status 2 on both runners. The
seven discovery failures were:

- `accounts_umask_etc_bashrc`;
- `accounts_umask_etc_profile`;
- `configure_crypto_policy`;
- `file_groupownership_system_commands_dirs`;
- `file_ownership_binary_dirs`;
- `network_configure_name_resolution`;
- `package_crypto-policies_installed`.

`security_patches_up_to_date` was `notchecked`. The follow-on review selected
the two program-ownership failures as genuine image-owned defects and excluded
the remaining findings at the appropriate host, deployment, or
alternative-evidence boundary. A profile `pass` was not treated as sufficient
evidence that a rule applies to a minimal container.

## Tailored profile and ownership fix

The committed profile at
`security/scap/datopsis-ubi9-micro-tailoring.xml` selects 36 checks covering
account databases, immutable executable and library ownership/modes,
world-writable or ungrouped content, legacy trust files, and deliberately
absent packages. It does not extend the upstream STIG profile, so no upstream
selection can silently become an adopted image check.

Discovery showed that the ClickHouse TGZ preserved its publisher's UID/GID
1000 on `/usr/bin/clickhouse` and related files. It also showed that the
repository copied the entrypoint as UID 101. Both are immutable programs, so
the Containerfile now normalizes `/runtime/usr` and repository-supplied `/usr`
assets to `0:0`. ClickHouse still runs as `101:0`; writable data, log,
configuration, and initialization directories retain their rootless contract.
Program ownership does not grant the process any additional privilege.

The complete selection and exclusion analysis is in the
[SCAP rule rationale](../security/scap/RULE-RATIONALE.md). Notably, RHEL system
crypto policy was not selected because installing its files would not prove
that the upstream static ClickHouse binary consumes that policy. DNS, runtime
logs, persistent storage, kernel, SELinux, FIPS mode, and platform facilities
remain deployment- or host-owned. Patch currency is evaluated through SBOM,
Trivy, Grype, pinned rebuilds, and vulnerability response rather than an
in-place package-manager rule.

### Initial tailored qualification

[GitHub Actions run 34162299349](https://github.com/datopsis/clickhouse-ubi/actions/runs/34162299349)
evaluated the profile on native AMD64 and ARM64 during pull-request review.
Each architecture produced exactly 36 `pass` and 1,504 `notselected` results,
OpenSCAP exit code 0, no operational error, and the same complete rule/result
inventory. Both summaries recorded tailoring SHA-256
`f6ab64233c73cdd136f70444eae71c2188ef618e51a5c5e9bd6a6e80653b8b22`.
The smoke suite also confirmed that ClickHouse still ran as UID 101 while
`/usr/bin`, `/usr/bin/clickhouse`, and the entrypoint were owned by `0:0`.

This pull-request run qualifies the implementation but does not count toward
the three required scheduled or `main` stabilization runs. That count starts
after merge and restarts whenever the content or tailoring changes.

## Profile maintenance method

The upstream RHEL 9 STIG profile remains a discovery input, not a statement
that every rule is applicable or inherited. Any profile revision must:

- classify every result as applicable, not applicable, inherited from the
  platform, pass, fail, error, or not checked;
- update the XCCDF tailoring version and deliberately review whether its stable
  Datopsis profile identifier remains compatible;
- update the rationale table mapping each selected rule to the image-owned
  file, package, account, or permission it evaluates;
- explicitly exclude host-only rules for the kernel, boot loader, partitions,
  mount layout, system services, audit subsystem, host firewall, host sysctls,
  SELinux enforcement mode, and FIPS mode;
- avoid automatic remediation, because remediation can silently mutate the
  image after its tested build steps and invalidate other evidence.

Candidate rule families include RPM/package integrity and signatures, account
and password-file permissions, empty-password checks, unexpected setuid/setgid
or world-writable files, service-account shells, and relevant crypto-policy
files. Exact rule IDs must come from the pinned data stream after discovery;
they must not be guessed from another RHEL content version.

## Enforcement rollout

SCAP integration should be incremental:

1. **Discovery:** publish complete reports without blocking while the tailoring
   and applicability decisions are reviewed.
2. **Stabilization:** require the scan to execute successfully on native AMD64
   and ARM64 for at least three scheduled or `main` runs. Evaluation errors
   always fail; selected-rule findings remain visible but temporarily
   non-blocking.
3. **Enforcement:** make failure of a selected, image-owned rule blocking. Keep
   exclusions and any accepted exception documented with owner, rationale, and
   review date.
4. **Drift review:** re-run discovery whenever the UBI major version, OpenSCAP
   engine, ComplianceAsCode data stream, or tailoring changes.

Before enforcement, compare one image digest's `OSCAP_PROBE_ROOT` result with
`oscap-podman` on a disposable RHEL 9 host. Investigate differences in platform
facts, applicability, and rule results. This is a qualification cross-check,
not a reason to give routine GitHub-hosted CI root access.

## Local tailored scan with Podman

Run this only on a native Linux AMD64 or ARM64 host with Podman, Bash, and
Python 3. Rootless Podman is sufficient if the host supports user namespaces
and delegated cgroups. The scan wrapper grants the four documented
filesystem/chroot capabilities only inside Podman's user namespace; it does
not require host root or start the ClickHouse image as root.

```console
git clone https://github.com/datopsis/clickhouse-ubi.git
cd clickhouse-ubi

ARCHITECTURE=amd64  # use arm64 on an ARM64 host
IMAGE="localhost/clickhouse-ubi:test-${ARCHITECTURE}"
SCANNER_IMAGE="localhost/datopsis-openscap:0.1.82-${ARCHITECTURE}"

podman build --format docker --platform "linux/${ARCHITECTURE}" \
  --file Containerfile --tag "${IMAGE}" .
podman build --format docker --platform "linux/${ARCHITECTURE}" \
  --file Containerfile.scap --tag "${SCANNER_IMAGE}" .

CONTAINER_RUNTIME=podman \
IMAGE="${IMAGE}" \
SCAP_SCANNER_IMAGE="${SCANNER_IMAGE}" \
ARCHITECTURE="${ARCHITECTURE}" \
SCAP_RESULTS_DIR="scap-results-${ARCHITECTURE}" \
  bash scripts/scap-scan.sh
```

Review `summary.json` first, then the HTML report and XML evidence. Confirm its
mode is `tailored-stabilization-report-only`, its profile ID is the Datopsis
profile above, and both hashes match the committed inputs. Confirm `rootfs.tar`
was removed. Do not commit the generated results. If rootless
Podman reports that memory limits are unsupported, qualify the host's cgroup
configuration; do not remove the CI limit without a documented risk review.

For a disconnected scan, build both images and run the wrapper while connected
once, save them with `podman save`, transfer the repository plus image archive
through the approved media process, load with `podman load`, and run the same
wrapper. Evaluation already uses `--network none`; no content fetch occurs.
Record and verify SHA-256 hashes for the repository commit/archive and saved
images at both sides of the transfer.

## RHEL `oscap-podman` qualification cross-check

On a disposable RHEL 9 test host with `openscap-utils`, `openscap-scanner`, and
`scap-security-guide` installed, use `oscap-podman` only for the planned
one-digest comparison. First load the exact CI-qualified target digest and copy
the reviewed tailoring file to the host. Then run:

```console
sudo oscap-podman <image-id-or-digest> xccdf eval \
  --profile <datopsis-profile-id> \
  --tailoring-file security/scap/datopsis-ubi9-micro-tailoring.xml \
  --results-arf results.arf.xml \
  --report report.html \
  /usr/share/xml/scap/ssg/content/ssg-rhel9-ds.xml
```

`oscap-podman` requires host root because it integrates with local container
storage. Use only a dedicated test host containing no unrelated workloads or secrets.
Record the exact image digest, host version, Podman/OpenSCAP versions, content
package version, tailoring hash, command, and sanitized results.

## Security boundaries beyond SCAP

SCAP complements rather than replaces vulnerability scanning, behavioral
tests, supply-chain verification, and deployment controls. Before the first
release, also complete a concise image threat model, review SBOM/package drift,
exercise secret and certificate rotation without log disclosure, and define a
base-image rebuild and vulnerability-response SLA.

The separate `clickhouse-production-stack` repository should own admission
policy for digest/signature/attestation verification, NetworkPolicy and egress
allowlists, platform TLS automation, secret-store integration, backup
encryption and immutable/off-site copies, restore tests, audit-log routing,
monitoring, and deployment-level incident response. Those controls cannot be
proven by scanning this image filesystem.

Authoritative references:

- [Red Hat RHEL 9 Security hardening: scanning container and container images](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/security_hardening/scanning-the-system-for-configuration-compliance-and-vulnerabilities_security-hardening)
- [OpenSCAP User Manual: scanning an arbitrary filesystem](https://static.open-scap.org/openscap-1.3/oscap_user_manual.html)
- [ComplianceAsCode content and container applicability](https://github.com/ComplianceAsCode/content)
