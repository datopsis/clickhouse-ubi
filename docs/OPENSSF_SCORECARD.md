# OpenSSF Scorecard

This repository treats OpenSSF Scorecard as a security signal, not a compliance target. Improvements must represent real controls; checks that do not fit a container-packaging repository are documented rather than simulated.

## Automated analysis

The `OpenSSF Scorecard` workflow runs on changes to `main`, branch-protection changes, a weekly schedule, and manual dispatch. It:

1. runs the SHA-pinned official Scorecard action;
2. publishes the result to the public Scorecard API so the README badge can update;
3. retains SARIF output for five days; and
4. uploads findings to GitHub code scanning.

The workflow follows the restrictions required for published Scorecard results: no workflow-level environment, read-only top-level permissions, and write permissions only on the analysis job. All actions are pinned to immutable commits and maintained by Dependabot.

The separate `CodeQL` workflow performs genuine static analysis of this repository's GitHub Actions workflows with the `security-extended` query suite. ShellCheck, Hadolint, Actionlint, Zizmor, Trivy, Syft, and Grype remain in CI because CodeQL does not replace their container-, inventory-, and shell-specific coverage.

## Where to view current results

The current public score and per-check details are in the [OpenSSF Scorecard viewer](https://securityscorecards.dev/viewer/?uri=github.com/datopsis/clickhouse-ubi). The [OpenSSF Scorecard workflow history](https://github.com/datopsis/clickhouse-ubi/actions/workflows/scorecard.yml) shows each run and exposes its downloadable SARIF artifact for five days. Uploaded findings are also available under the repository's **Security > Code scanning** page to users with the required GitHub access.

This file documents the repository's policy, controls, initial baseline, and expected score movement. It is not a copy of the live report; use the viewer or the latest workflow run for current results.

## Baseline and expected movement

The initial local measurement on 2026-09-06 used Scorecard 5.5.0 against commit `848ddb21e9b41a9adef09da015cc19fabd71bc66` and scored **5.2/10**. A new repository starts low because several checks depend on historical evidence rather than files.

| Check | Baseline | Repository control or next action |
| --- | ---: | --- |
| Binary-Artifacts | 10 | Keep generated binaries and archives out of Git. |
| Branch-Protection | 0 | The active ruleset now requires pull requests, resolved threads, and up-to-date `lint` and `image` checks. A 2026-09-06 verification run scored 4; remaining points require the deliberately deferred review controls below. |
| CI-Tests | N/A | Merge changes through pull requests with the `lint` and `image` jobs passing. |
| CII-Best-Practices | 0 | Register the project at Best Practices when its public project details are ready. |
| Code-Review | 0 | Use reviewed pull requests; direct commits do not create review evidence. |
| Contributors | 0 | This rises through genuine contributions from independent organizations. |
| Dangerous-Workflow | 10 | Keep Zizmor and CodeQL blocking and avoid untrusted input in privileged workflows. |
| Dependency-Update-Tool | 10 | Dependabot covers Actions, pre-commit hooks, and hash-locked CI Python tools. |
| Fuzzing | 0 | No useful fuzz target exists yet for this shell/container packaging. Add fuzzing only with a meaningful parser or executable target. |
| License | 10 | Apache-2.0 is stored in the repository root. |
| Maintained | 0 | Repositories younger than 90 days receive zero; normal maintenance creates the evidence over time. |
| Packaging | 10 | Tagged builds publish the container through GitHub Actions. |
| Pinned-Dependencies | 9 | The initial un-hashed pip install is replaced by a fully hash-locked requirements file; reruns should report 10. |
| SAST | 0 | The CodeQL Actions workflow supplies detectable SAST evidence after it runs. |
| Security-Policy | 10 | `SECURITY.md` documents private reporting and disclosure expectations. |
| Signed-Releases | N/A | The first tagged GitHub release will include `.sigstore.json` and `.intoto.jsonl` evidence. |
| Token-Permissions | 0 | Write access is moved from workflow scope to the release job; reruns should report 10. |
| Vulnerabilities | 10 | Trivy and Grype gate high/critical findings under the [UBI-installable fix policy](../SECURITY.md#ubi-installable-fix-gate), while Scorecard also checks OSV data. |

Scores can change when Scorecard changes its checks or when repository history changes. Review the individual findings instead of treating the aggregate number as a permanent guarantee.

## Required `main` ruleset

Repository rules are GitHub settings and cannot be represented by a committed file. The active `Protect main` ruleset targets the default branch, requires a pull request and resolved review threads, requires successful and up-to-date `lint` and `image` checks, blocks force pushes and deletion, and has no bypass actors. Required approvals remain zero so either maintainer can contribute without needing two other available people.

To reach the highest Scorecard branch-protection tier, extend the ruleset with:

- at least two approvals;
- stale approvals dismissed when new commits are pushed;
- approval required for the most recent reviewable push;
- Code Owner review required, using `.github/CODEOWNERS`.

These settings match the highest Scorecard branch-protection tier. A second collaborator is now present, but required review enforcement is intentionally deferred for the first release at the maintainer's request. Two independent approvals would require at least three regularly available maintainers to avoid deadlocking an author's pull request. The current exception and revisit point are tracked in [ROADMAP.md](ROADMAP.md); never enable or weaken the review rules merely to change a score.

After changing the ruleset, manually run the affected workflows, then trigger `OpenSSF Scorecard`. Confirm the required-check names against GitHub's ruleset UI because GitHub derives them from completed check runs. `Analyze GitHub Actions` is not required because its path-filtered workflow intentionally does not run on ordinary pull requests; making a conditional check required would block those changes.

## GitHub security settings

Keep these repository settings enabled under **Settings > Code security and analysis**:

- dependency graph and Dependabot alerts;
- Dependabot security updates;
- secret scanning;
- push protection for detected secrets; and
- private vulnerability reporting.

Secret scanning, push protection, Dependabot security updates, and private vulnerability reporting were verified enabled on 2026-09-06. The security policy directs reporters to GitHub private advisories. Verify these settings again after repository transfers or visibility changes.

## Pull request and release practice

All changes to `main` must enter through pull requests with the required checks. Reviewers should verify pinned dependency updates, security-sensitive workflow permissions, container provenance, and changelog entries. An emergency that requires relaxing the ruleset must be time-bounded, approved by a maintainer, recorded in the pull request, and reverted immediately afterward.

Release identifiers, version increments, and the treatment of repository-only changes are defined in [VERSION.md](VERSION.md). The tag workflow publishes an immutable multi-architecture image, scans it with Trivy and Grype, generates a downloadable Syft SBOM, attaches OCI SBOM and provenance attestations, signs the digest with GitHub OIDC, and creates a GitHub release with:

- `image.spdx.json`, the Syft-generated SPDX JSON inventory;
- `image.sigstore.json`, the keyless signature verification bundle; and
- `image.intoto.jsonl`, the downloaded in-toto attestations.

Do not create source-only GitHub releases manually. Scorecard evaluates recent releases consistently, so an unsigned manual release lowers the Signed-Releases result.

## Run Scorecard locally

Use a GitHub token with read access. Do not place the token on the command line or commit it to an environment file.

```bash
export GITHUB_AUTH_TOKEN="$(gh auth token)"
podman run --rm \
  --env GITHUB_AUTH_TOKEN \
  ghcr.io/ossf/scorecard:v5.5.0@sha256:2ad2ced1cc8d080a589fac211944834c0da3dd82a4d7b0e70a642b6be76987d7 \
  --repo=github.com/datopsis/clickhouse-ubi \
  --show-details
unset GITHUB_AUTH_TOKEN
```

For machine-readable output, add `--format=json`. The public result is available from the [Scorecard viewer](https://securityscorecards.dev/viewer/?uri=github.com/datopsis/clickhouse-ubi) after the publishing workflow completes.

## Review cadence

Review Scorecard findings at least monthly and before each release. For every decrease:

1. inspect the detailed finding and referenced file or GitHub setting;
2. decide whether it identifies a real risk for this repository;
3. remediate real risks through a reviewed pull request; and
4. document intentional exceptions in this file with the reason and compensating controls.

Authoritative references:

- [OpenSSF Scorecard checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md)
- [Scorecard Action setup and publishing restrictions](https://github.com/ossf/scorecard-action#manual-action-setup)
- [OpenSSF Best Practices Badge](https://www.bestpractices.dev/)
- [GitHub repository rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
