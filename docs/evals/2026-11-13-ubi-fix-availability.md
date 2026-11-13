# UBI fix availability verification

## Decision and source

Apply the owner's 2026-11-12 organization rule, following
[sail-ubi #4](https://github.com/datopsis/sail-ubi/pull/4), merge commit
`861d92fb12e1a8b25c728da93129efdc770fd540`. RPM deferral requires a successful
negative repository query. Every error and every fixable non-RPM finding remains
blocking. Trivy secret detection and the independent SCAP execution check remain blocking.

Unlike the reference repository's explicit two-repository configuration, this
repository's pinned UBI Minimal builder ships **three** enabled repositories:
BaseOS, AppStream, and CodeReady Builder. Verified by reading `/etc/yum.repos.d/ubi.repo`
from the pinned image, not by inferring configuration from public CDN URLs.
The query runs inside that pinned image and shares its configuration loader
with lock regeneration. Repository hashes, URLs, and candidate EVRs are retained.

## Local and live checks

- 36 Python tests pass, including the subprocess suite exercising actual librpm
  EVR comparison and DNF failures. Release-tag and entrypoint-path shell tests pass.
- Pre-commit checks pass, including YAML, actionlint, shellcheck, hadolint, LF
  endings, and RPM lock/base consistency.
- A local live check used the exact extracted UBI repository file with the host
  DNF bindings: 32 available-version queries and 32 synthetic future-epoch
  unavailable-version queries per architecture (128 total). Every case passed.
  This checks actual metadata, while native CI repeats the queries with the
  pinned UBI image's own DNF/librpm bindings.
- [Main lock proposal](https://github.com/datopsis/clickhouse-ubi/actions/runs/43423279852)
  regenerated both architectures twice with `scripts/update-rpm-lock.sh` and
  compared identical outputs. The lock retains 32 RPMs on each architecture;
  10 versions per architecture change. Exact URLs, SHA-256 hashes and RPM
  identities are validated by normal tooling, and native builds verify signatures.
- The initial PR resolver correctly failed closed on an incomplete expected repo
  set. Inspecting the pinned image established that CodeReady Builder must be
  included; subsequent runs verify the corrected three-repository configuration.

## Boundaries

The lock changes image contents. The next published image needs a new packaging
revision under `docs/VERSION.md`; this PR does not create a release or tag.
The pinned base references and ClickHouse version are unchanged. UBI's rolling
9 repositories now publish `redhat-release` 9.9, which the refreshed overlay uses.

No GitHub settings, required job names, runtime hardening, or vulnerability
exemptions change. Tracking issue writes are intentionally skipped on PRs.
Scheduled issue updates and tag-triggered publication/signing remain unverified
until the workflows run on trusted main/a release tag. Unit tests cover issue
creation, no-op updates, publication/removal, closure/reopening, missing evidence,
and vendor-version changes. A changed job result or unfixed/blocking inventory
alone does not trigger a tracking comment.

## Native scanner evidence

[PR #30](https://github.com/datopsis/clickhouse-ubi/pull/30) records the native
before/after run links and per-scanner, per-architecture counts. The baseline
[run 43423845975](https://github.com/datopsis/clickhouse-ubi/actions/runs/43423845975)
uses main's unchanged image inputs and RPM lock, with complete report collection
added. The after run uses the refreshed lock. Counts are scanner finding records,
not deduplicated CVE IDs; gate counts use High/Critical severity. No claim of
remediation or deferral is inferred from workflow status alone.


Both the baseline and [after run 43424922716](https://github.com/datopsis/clickhouse-ubi/actions/runs/43424922716)
passed native AMD64/ARM64 CI. Downloaded and read the actual Trivy 0.70.0,
Grype 0.118.0, admission, live-query and SPDX reports from both runs.

High/Critical counts are **fixable blocking / deferred / unfixed**:

| Architecture | Scanner | Before | After |
| --- | --- | --- | --- |
| amd64 | Trivy | 0 / 0 / 0 | 0 / 0 / 0 |
| amd64 | Grype | 0 / 0 / 0 | 0 / 0 / 0 |
| arm64 | Trivy | 0 / 0 / 0 | 0 / 0 / 0 |
| arm64 | Grype | 0 / 0 / 0 | 0 / 0 / 0 |

At all severities, per architecture, Trivy fixable findings decreased from 14
(13 Medium, 1 Low) to zero, with 15 unfixed unchanged (6 Medium, 9 Low).
Grype fixable findings decreased from 5 (4 Medium, 1 Low) to zero, with 18
unfixed unchanged (9 Medium, 9 Low). Trivy reported zero secrets; both scanners reported zero
High/Critical vulnerabilities. No real High/Critical deferrals existed in these
images; unavailable-fix behavior is verified by tests and synthetic future-epoch
live queries, not by claiming an advisory is deferred.

Each native runner passed 32 positive and 32 negative queries with the pinned
UBI DNF/librpm. Both configurations have SHA-256
`f59e1e4c2f20048ef3204f5c81d23b04aac53a7d789b1f4d055a937867109f13` and
architecture-specific URLs for all three repositories. SPDX inventories match
all 32 locked RPM identities on both architectures before and after (imported
RPM signing keys are separate metadata).

[Corrected PR lock regeneration](https://github.com/datopsis/clickhouse-ubi/actions/runs/43424923166)
resolved each architecture twice and produced an empty patch against the
committed lock. Lint and CodeQL passed; the issue job was skipped on the PR.
The all-severity Grype action warns about remaining Low/Medium findings; those
are retained, not suppressed. The baseline also had a benign concurrent-cache
reservation warning.

Retained after artifacts: [AMD64](https://github.com/datopsis/clickhouse-ubi/actions/runs/43424922716/artifacts/14037770751)
and [ARM64](https://github.com/datopsis/clickhouse-ubi/actions/runs/43424922716/artifacts/14037905510).
The subsequent commit only aligns operator documentation and records these
measurements; image inputs and gate implementation are unchanged.
