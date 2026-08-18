# NVIDIA/OpenShell: Last 5 Merged Pull Requests
## Executive Summary
The five latest merged pull requests span provider credential stability, OCSF AI inference observability, repository hygiene, macOS Podman build coverage, and L7 request-path security hardening. Three PRs carried the `test:e2e` label (#2780, #2664, #2699); two had no labels (#2774, #2789). Two PRs explicitly linked GitHub issues: #2780 closes #2777, and #2664 closes #2663 while relating to #2662. The remaining three PR bodies state that no issue was required.

## PR #2780: fix(providers): keep refresh credential handles stable
- URL: https://github.com/NVIDIA/OpenShell/pull/2780
- Merged: 2026-08-18T21:00:13Z
- Author: mrunalp
- Labels: test:e2e
- Associated issues: #2777 (closed)
### What changed
- Kept gateway-managed refresh credentials usable for long-running sandbox processes across short-lived access-token rotations.
- Introduced identity-stable workload credential handles whose resolved value advances to the current token.
- Added a durable authorization epoch to gateway refresh configuration, with migration fallback for existing records.
- Derived per-sandbox credential handles from provider identity, credential key, authorization epoch, and canonical endpoint boundary.
- Ensured explicit refresh reconfiguration, provider replacement, refresh deletion, or endpoint-boundary changes rotate or revoke handles so stale processes fail closed.
- Added unit, integration, and Podman E2E coverage, including 12 token rotations, supervisor-state reconstruction, and reconfiguration revocation.
- Updated architecture, provider, and OpenShell CLI skill documentation for stable handle lifecycle and rollout behavior.
### Larger task context
This PR directly closes accepted bug #2777, which describes long-running processes losing provider access after credential refresh and is labeled for provider and supervisor areas. That issue linkage provides the evidence that the PR is part of a tracked provider/supervisor reliability fix.

## PR #2664: feat(ocsf): emit AI inference events via ai_operation profile on ApiActivity [6003], bump schema to v1.8.0
- URL: https://github.com/NVIDIA/OpenShell/pull/2664
- Merged: 2026-08-18T16:43:07Z
- Author: zanetworker
- Labels: test:e2e
- Associated issues: #2663 (closed), #2662 (open)
### What changed
- Added OCSF AI inference event emission when the inference proxy routes model calls through `inference.local`.
- Used the official OCSF v1.8.0 `ai_operation` profile on `ApiActivity` class [6003], and bumped `OCSF_VERSION` to `1.8.0`.
- Added `AiModel`, `ApiActivityEvent`, builder support, shorthand formatting, schema validation handling for profile-gated fields, and vendored OCSF v1.8.0 schemas.
- Emitted inference events from `openshell-supervisor-network` after inference calls complete, including model and latency data and token counts where available on buffered responses.
- Scoped the change to governed inference traffic through `inference.local`; direct CONNECT tunnels and older SIEM compatibility were explicitly out of scope.
- Reported successful crate tests, workspace clippy, and Kubernetes E2E validation in the PR body.
### Larger task context
This PR closes accepted feature issue #2663 for emitting OCSF v1.8.0 `ai_operation` events from the inference proxy. It also explicitly relates to accepted, open issue #2662 for configurable OCSF schema versions for SIEM compatibility; the PR body states that backward compatibility for older SIEM consumers is out of scope and tracked there.

## PR #2774: chore(sdk/go): remove coverage.out from tracking
- URL: https://github.com/NVIDIA/OpenShell/pull/2774
- Merged: 2026-08-18T12:09:09Z
- Author: rhuss
- Labels: none
- Associated issues: none identified
### What changed
- Removed `sdk/go/coverage.out` from git tracking.
- Identified the file as an accidentally committed `go test -coverprofile` artifact.
- Relied on the existing `.gitignore` coverage for `coverage.out` to prevent future commits.
- Confirmed the change was mechanical and did not modify code.
### Larger task context
No larger task context is evidenced. The PR body explicitly says no issue was required and describes the work as a mechanical cleanup of an accidentally committed test artifact; there are no labels or milestone on the PR.

## PR #2789: fix(driver-podman): compile container spec on macOS
- URL: https://github.com/NVIDIA/OpenShell/pull/2789
- Merged: 2026-08-18T12:06:57Z
- Author: elezar
- Labels: none
- Associated issues: none identified
### What changed
- Fixed a macOS Podman driver compilation failure involving an unconditional Podman container-spec function signature.
- Imported `Path` unconditionally because it is used in that unconditional signature.
- Extended the existing macOS Clippy guard to include db-credstore, Docker, Kubernetes, Kubernetes Secrets, Podman, and Vault driver crates.
- Kept the VM driver excluded because its build script embeds runtime assets.
- Validated workflow YAML parsing and `git diff --check`; local `mise`/`cargo` tests were not run because those tools were unavailable in the author’s shell.
### Larger task context
No larger task context is evidenced. The PR body states no issue was required and characterizes the change as localized CI coverage maintenance plus an obvious compilation fix following a release-build regression. The body links regression workflow runs, but no issue, label, or milestone identifies a larger tracked task.

## PR #2699: fix(supervisor-network): canonicalize dot-segments before policy evaluation
- URL: https://github.com/NVIDIA/OpenShell/pull/2699
- Merged: 2026-08-17T23:21:55Z
- Author: alangou
- Labels: test:e2e
- Associated issues: none identified
### What changed
- Fixed L7 request-target canonicalization so path parameters are stripped before dot-segment resolution.
- Added a residual guard rejecting any `.` or `..` segment that survives canonicalization via `CanonicalizeError::ResidualDotSegment`.
- Updated module documentation to state the ordering requirement and no-residual-dot-segment invariant used by the policy engine.
- Scoped `allow_encoded_slash` to the matched L7 endpoint rather than applying an opt-in across every config sharing a `host:port`.
- Added helper logic to detect encoded-slash sentinels precisely and reject `%2F` when the matched endpoint did not opt in.
- Added unit and relay integration tests covering dot-segment/path-parameter cases, percent-encoded forms, encoded-slash handling, and multi-endpoint route selection.
### Larger task context
No larger task context is evidenced. The PR body states no issue was required because it is a security fix, and the PR has no milestone. The `test:e2e` label supports test coverage but does not identify a larger task relationship.

## Evidence Index

This index is rendered deterministically from GitHub API fields.

| Pull request | PR labels | Milestone | Associated issues | Related pull requests | Workstream labels |
|---|---|---|---|---|---|
| [#2780](https://github.com/NVIDIA/OpenShell/pull/2780) | `test:e2e` | none | [#2777](https://github.com/NVIDIA/OpenShell/issues/2777) (closed; labels: `area:supervisor`, `test:e2e`, `area:providers`, `state:accepted`) | none | none |
| [#2664](https://github.com/NVIDIA/OpenShell/pull/2664) | `test:e2e` | none | [#2663](https://github.com/NVIDIA/OpenShell/issues/2663) (closed; labels: `state:accepted`); [#2662](https://github.com/NVIDIA/OpenShell/issues/2662) (open; labels: `state:accepted`) | none | none |
| [#2774](https://github.com/NVIDIA/OpenShell/pull/2774) | none | none | none | none | none |
| [#2789](https://github.com/NVIDIA/OpenShell/pull/2789) | none | none | none | none | none |
| [#2699](https://github.com/NVIDIA/OpenShell/pull/2699) | `test:e2e` | none | none | none | none |
