# UBI fix availability verification

## Decision and source

Apply the owner's 2026-11-12 organization rule, following
[sail-ubi #4](https://github.com/datopsis/sail-ubi/pull/4), merge commit
`861d92fb12e1a8b25c728da93129efdc770fd540`. RPM deferral requires a successful
negative repository query. Every error and every fixable non-RPM finding remains
blocking. Trivy secret detection and the independent SCAP check remain blocking.

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
