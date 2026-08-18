# NVIDIA/OpenShell: Last 5 Merged Pull Requests
## Executive Summary
The five most recently merged NVIDIA/OpenShell pull requests include one OCSF/AI observability feature, two supervisor or driver fixes, one repository hygiene chore, and one documentation workflow update. PR #2664 is the only selected PR with explicitly linked GitHub issues: it closes #2663 and relates to #2662. PRs #2774, #2789, and #2699 explicitly state that no issue was required, and PR #2687 links no issue in its body. Only PR #2664 has evidence of broader tracked work through its linked issues; PR #2699 is a security fix, but no linked issue, milestone, or larger-task relationship is stated.

## PR #2664: feat(ocsf): emit AI inference events via ai_operation profile on ApiActivity [6003], bump schema to v1.8.0
- URL: https://github.com/NVIDIA/OpenShell/pull/2664
- Merged: 2026-08-18T16:43:07Z
- Author: zanetworker
- Labels: test:e2e
- Associated issues: #2663 “feat: Emit OCSF v1.8.0 ai_operation events from inference proxy” (closed, labels: state:accepted); #2662 “feat: Configurable OCSF schema version for SIEM compatibility (v1.1/v1.3)” (open, labels: state:accepted)
### What changed
This PR adds OCSF AI inference event emission for model calls routed through `inference.local`. It uses the OCSF v1.8.0 `ai_operation` profile attached to `ApiActivity` class 6003, and bumps the repository’s OCSF version to `1.8.0`.

The `openshell-ocsf` changes add AI-model and API-activity support, including an `AiModel` object, optional `ai_model` field on base events, an `ApiActivityEvent`, an `ApiActivityBuilder` with `.ai_model()`, shorthand formatting for inference activity, re-exports, schema validation changes for profile-gated fields, and vendored OCSF v1.8.0 schemas for the relevant class/object/profile.

The `openshell-supervisor-network` changes emit AI inference events after proxied inference calls complete. Buffered responses include model and token counts from the response body; streaming responses include model and latency, with token counts omitted because SSE chunks are not accumulated. The PR body lists passing tests for `openshell-ocsf`, `openshell-supervisor-network`, workspace Clippy, and Kubernetes E2E coverage.
### Larger task context
This PR is part of a tracked AI observability task because it explicitly closes issue #2663, “feat: Emit OCSF v1.8.0 ai_operation events from inference proxy.” It is also explicitly related to issue #2662, which tracks configurable OCSF schema version support for SIEM backward compatibility. The PR body states that backward compatibility for v1.1/v1.3 consumers is out of scope for this PR and tracked in #2662.

## PR #2774: chore(sdk/go): remove coverage.out from tracking
- URL: https://github.com/NVIDIA/OpenShell/pull/2774
- Merged: 2026-08-18T12:09:09Z
- Author: rhuss
- Labels: None
- Associated issues: None
### What changed
This PR removes `sdk/go/coverage.out` from git tracking. The body describes the file as a `go test -coverprofile` artifact that was accidentally committed and already covered by `.gitignore`. The listed change is `git rm --cached sdk/go/coverage.out`, with verification that `git ls-files sdk/go/coverage.out` returns empty afterward and that `.gitignore` prevents future commits of `coverage.out`.
### Larger task context
No larger tracked task is evidenced. The PR body explicitly says “No issue required” and characterizes the work as a mechanical cleanup of an accidentally committed test artifact. There are no labels, milestone, linked issues, or explicit body relationships indicating a larger task.

## PR #2789: fix(driver-podman): compile container spec on macOS
- URL: https://github.com/NVIDIA/OpenShell/pull/2789
- Merged: 2026-08-18T12:06:57Z
- Author: elezar
- Labels: None
- Associated issues: None
### What changed
This PR fixes a macOS Podman driver compilation failure and broadens macOS Clippy coverage to catch similar `cfg` regressions before release builds. The body says it imports `Path` unconditionally because it appears in an unconditional Podman container-spec function signature.

It also adds the db-credstore, Docker, Kubernetes, Kubernetes Secrets, Podman, and Vault driver crates to macOS Clippy, while keeping the VM driver excluded because its build script embeds runtime assets. The PR body cites regression evidence through GitHub Actions links for an original macOS release build failure and a macOS Rust lint run, but those are workflow run links rather than GitHub issues.
### Larger task context
No larger tracked task is evidenced. The PR body explicitly says “No issue required” and describes the change as localized CI coverage maintenance plus an obvious compilation fix following a release-build regression. There are no labels, milestone, linked issues, or explicit body relationships indicating a larger task.

## PR #2699: fix(supervisor-network): canonicalize dot-segments before policy evaluation
- URL: https://github.com/NVIDIA/OpenShell/pull/2699
- Merged: 2026-08-17T23:21:55Z
- Author: alangou
- Labels: test:e2e
- Associated issues: None
### What changed
This PR fixes an L7 request-target canonicalization bug where a canonical path could still contain `.` or `..` segments. Because that canonical path is used both as OPA policy input and as the bytes forwarded upstream, residual dot-segments could allow a request to escape the path prefix allowed by policy.

The changes reorder canonicalization so path parameters are stripped before dot-segment resolution, add a `CanonicalizeError::ResidualDotSegment` guard to reject any surviving `.` or `..`, extract and reuse `strip_path_parameters`, update module documentation, and add or update tests around path-parameter and encoded-dot cases. The PR also scopes `allow_encoded_slash` behavior to the L7 endpoint that actually matched, adding a helper to detect encoded-slash sentinels and re-checking after config selection in `l7/relay.rs` and `proxy.rs`.

The PR body reports `mise run ci` as green, with lint, compile, and tests passing. It specifically mentions 31 tests in `l7::path`, relay integration coverage for endpoints sharing one `host:port`, and E2E applicability marked complete.
### Larger task context
No larger tracked task is evidenced. The PR body explicitly says “No issue required: security fix” and references `SECURITY.md`, but it does not link a GitHub issue, milestone, or explicit larger-task relationship. Therefore this should be treated as a standalone security fix rather than part of a larger tracked task.

## PR #2687: Update docs.yml to remove warning banner
- URL: https://github.com/NVIDIA/OpenShell/pull/2687
- Merged: 2026-08-17T22:59:40Z
- Author: kirit93
- Labels: None
- Associated issues: None
### What changed
This PR updates `docs.yml` to remove a warning banner from the documentation page. The PR body is brief and states only: “Remove warning banner from docs page.”
### Larger task context
No larger tracked task is evidenced. The PR body links no issue and provides no milestone, label, or explicit relationship indicating broader tracked work.

## Evidence Index

This index is rendered deterministically from GitHub API fields.

| Pull request | PR labels | Milestone | Associated issues | Related pull requests | Workstream labels |
|---|---|---|---|---|---|
| [#2664](https://github.com/NVIDIA/OpenShell/pull/2664) | `test:e2e` | none | [#2663](https://github.com/NVIDIA/OpenShell/issues/2663) (closed; labels: `state:accepted`); [#2662](https://github.com/NVIDIA/OpenShell/issues/2662) (open; labels: `state:accepted`) | none | none |
| [#2774](https://github.com/NVIDIA/OpenShell/pull/2774) | none | none | none | none | none |
| [#2789](https://github.com/NVIDIA/OpenShell/pull/2789) | none | none | none | none | none |
| [#2699](https://github.com/NVIDIA/OpenShell/pull/2699) | `test:e2e` | none | none | none | none |
| [#2687](https://github.com/NVIDIA/OpenShell/pull/2687) | none | none | none | none | none |
