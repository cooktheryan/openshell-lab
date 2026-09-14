# NVIDIA/OpenShell: Last 5 Merged Pull Requests
## Executive Summary
The five most recent merged pull requests focus on deployment TLS support, certificate compatibility, CI portability, and isolation-runtime architecture. Two PRs improve TLS behavior: PR #2728 adds optional Helm BackendTLSPolicy support for Gateway API deployments, while PR #3286 updates generated gateway PKI for Python 3.13/RFC 5280 compatibility. Two PRs restore platform CI health on macOS and Windows. PR #3151 is the only selected PR explicitly tied to a larger tracked issue, advancing the Isolation Backend work under issue #1737.

## PR #2728: feat(helm): add BackendTLSPolicy support
- URL: https://github.com/NVIDIA/OpenShell/pull/2728
- Merged: 2026-09-14T17:58:47Z
- Author: bsquizz
- Labels: none
- Associated issues: none identified
### What changed
Added optional Helm support for Gateway API BackendTLSPolicy so a Gateway proxy can terminate client-facing TLS and re-encrypt traffic to the OpenShell gateway pod while validating the backend certificate. The chart now can auto-create a backend CA ConfigMap, order cert-manager resources before certgen hooks, poll for certificate issuance, enforce a configurable timeout, and fail fast by default when BackendTLSPolicy setup is incomplete. It also adds validation to reject the invalid combination of `server.tls.enableMtls=true` with `grpcRoute.backendTLSPolicy.enabled=true`, plus documentation for troubleshooting missing backend CA/SDS TLS errors.
### Larger task context
No larger tracked task is evidenced by an issue, label, milestone, or explicit body relationship. The body frames this as an optional deployment path for OpenShift 4.22+ and other platforms with BackendTLSPolicy support.

## PR #3286: fix(bootstrap): emit RFC 5280 extensions on generated gateway PKI
- URL: https://github.com/NVIDIA/OpenShell/pull/3286
- Merged: 2026-09-14T17:10:59Z
- Author: maxdubrinsky
- Labels: none
- Associated issues: none identified
### What changed
Updated generated gateway PKI so new certificates include extensions needed for stricter Python 3.13 X.509/TLS behavior. The PR sets CA `key_usages`, enables `use_authority_key_identifier_extension` for client and server certificates, and adds tests to verify the behavior.
### Larger task context
No larger tracked task is evidenced by an issue, label, milestone, or explicit body relationship. The only body context is that the compatibility problem was found during a Python 3.13 upgrade in `nemo-platform`.

## PR #3294: fix(ci): restore mise run ci on macOS
- URL: https://github.com/NVIDIA/OpenShell/pull/3294
- Merged: 2026-09-12T00:36:13Z
- Author: krishicks
- Labels: none
- Associated issues: none identified
### What changed
Made CI-related scripts and tests more portable for macOS. The changes replace BSD-incompatible in-place `sed` usage with temp-file rewrites, remove test-only shell interception, capture generated gateway config directly, allow parity tests to use supplied supervisor binaries, normalize temporary-directory paths, use portable RPM config installation, and set a valid `setuptools-scm` version for Python protobuf generation in Jujutsu checkouts. The body reports testing with `mise run ci` on linux/amd64 in an OpenShell sandbox.
### Larger task context
No larger tracked task is evidenced by an issue, label, milestone, or explicit body relationship. This appears to be a localized CI portability restoration.

## PR #3288: fix(ci): restore Windows test portability
- URL: https://github.com/NVIDIA/OpenShell/pull/3288
- Merged: 2026-09-11T21:59:50Z
- Author: pimlock
- Labels: test:windows
- Associated issues: none identified
### What changed
Restored portability for Windows MSVC checks and native-Windows pre-commit behavior. The PR updates an OCSF device OS-name test to expect the build platform, restores a Unix-only guard on a FIFO test using `nix::unistd::mkfifo`, skips a Unix shell-based Cargo lockfile check on native Windows, and uses npm's Windows `buf.cmd` shim for `proto:lint`. The body reports native Windows pre-commit, Windows x64 tests, and Rust lint validation.
### Larger task context
The meaningful label `test:windows` and the body place this work in the Windows test/CI portability area. The body characterizes it as a localized correction to regressions introduced by #3015 and #2814, not as part of a larger tracked task.

## PR #3151: feat(isolation): split supervisor and sandbox runtimes
- URL: https://github.com/NVIDIA/OpenShell/pull/3151
- Merged: 2026-09-11T21:09:25Z
- Author: drew
- Labels: test:e2e
- Associated issues: #1737 (open)
### What changed
Split the runtime into `openshell-supervisor`, running outside the agent workload, and `openshell-sandbox`, running inside it. The supervisor now consumes the Isolation Backend and owns policy, credentials, gateway access, DNS resolution, and upstream TCP dialing, while the sandbox owns the agent process tree, binary observation, Landlock, seccomp interception, and the OpenShell Sandbox Protocol. The gateway issues separate gateway and sandbox JWTs for a launch session; the supervisor refreshes them together, reconnects with a higher credential epoch, and fails closed if authentication expires or the channel is lost.
### Larger task context
This PR is explicitly part of issue #1737, “feat: establish the Isolation Backend interface,” which is labeled `area:sandbox` and `rfc`. The PR body also presents it as item 3 in a stack of isolation-related PRs, between the Isolation Backend contract and later VM, Docker, Kubernetes proxy-pod, Podman, and performance-harness work.

## Evidence Index

This index is rendered deterministically from GitHub API fields.

| Pull request | PR labels | Milestone | Associated issues | Related pull requests | Workstream labels |
|---|---|---|---|---|---|
| [#2728](https://github.com/NVIDIA/OpenShell/pull/2728) | none | none | none | none | none |
| [#3286](https://github.com/NVIDIA/OpenShell/pull/3286) | none | none | none | none | none |
| [#3294](https://github.com/NVIDIA/OpenShell/pull/3294) | none | none | none | none | none |
| [#3288](https://github.com/NVIDIA/OpenShell/pull/3288) | `test:windows` | none | none | none | none |
| [#3151](https://github.com/NVIDIA/OpenShell/pull/3151) | `test:e2e` | none | [#1737](https://github.com/NVIDIA/OpenShell/issues/1737) (open; labels: `area:sandbox`, `rfc`) | none | none |
