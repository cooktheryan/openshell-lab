# NVIDIA/OpenShell: Last 5 Merged Pull Requests
## Executive Summary
The five latest merged PRs span one major policy-language consolidation, two developer tooling fixes, and two test-infrastructure additions. PR #3334 is the largest functional change: it centralizes authored policy parsing and validation behind a shared `openshell-policy-schema` crate and closes issue #3333. PRs #3354 and #3385 are localized maintenance changes for Python development tasks under `jj` and for `mise` version compatibility. PRs #3372 and #3371 expand VM-based container-runtime qualification infrastructure and are explicitly tied to Fedora Podman and clean-install qualification issues #2973, #2974, and #2976.

## PR #3334: feat(policy): establish one canonical authored policy representation
- URL: https://github.com/NVIDIA/OpenShell/pull/3334
- Merged: 2026-09-16T17:58:57Z
- Author: johnnygreco
- Labels: area:policy, test:e2e, topic:compatibility
- Associated issues: #3333 (closed)
### What changed
This PR introduced `openshell-policy-schema` as the shared, dependency-light representation for OpenShell authored YAML/JSON policy documents. The CLI, runtime policy engine, supervisor disk loader, and prover now use common decoding rules, parser limits, authored-presence semantics, intrinsic validation, and conversion boundaries.

It also made policy ingestion fail closed for unknown fields in closed policy objects, while preserving arbitrary keys only in schema-defined user-data maps. The PR added bounded parsing/loading, path normalization, MCP revision vocabulary, protobuf/runtime conversions, legacy prover projection from the shared `PolicyDocument`, and documentation of schema boundaries and compatibility corrections. Regression coverage was added for unknown-field handling, parser budgets, authored presence, protobuf normalization, process identity export combinations, and supervisor fallback behavior.
### Larger task context
The PR explicitly closes #3333, which has the same policy-schema title and is labeled `area:policy`, `test:e2e`, and `topic:compatibility`. No milestone or additional broader-task relationship was provided.

## PR #3354: fix(python): stabilize development tasks under jj
- URL: https://github.com/NVIDIA/OpenShell/pull/3354
- Merged: 2026-09-16T16:47:04Z
- Author: krishicks
- Labels: none
- Associated issues: none identified
### What changed
This PR stabilizes Python development tasks when using `jj` as a Git frontend. The body explains that `setuptools-scm` can select `jj`'s Git-bridge development tag when `uv` resolves the local package, so the PR pins a development-only version for Python tasks that perform that resolution.

The PR clarifies that `0.0.0` is valid metadata for local editable development tasks, is not a release version or Git tag, and does not affect wheel builds, which remain unpinned and derive their version from the actual release tag.
### Larger task context
No issue, label, milestone, or explicit multi-PR relationship was provided. This appears to be a localized developer-tooling fix based only on the PR body.

## PR #3385: chore(tools): upgrade mise to 2026.9.9
- URL: https://github.com/NVIDIA/OpenShell/pull/3385
- Merged: 2026-09-16T16:04:51Z
- Author: krishicks
- Labels: none
- Associated issues: none identified
### What changed
This PR upgrades `mise` to version `2026.9.9`. The stated reason is that newer versions of `mise` modify `mise.lock`, causing PR failures for contributors with newer `mise` installations.

The PR body notes that CI was expected to fail before merge because the `Dockerfile.ci` image would not be rebuilt until after the PR landed.
### Larger task context
No issue, label, milestone, or explicit larger-task relationship was provided. The evidence supports classifying this as a localized tooling maintenance update.

## PR #3372: test(tmachine): run smoke tests from nextest archives
- URL: https://github.com/NVIDIA/OpenShell/pull/3372
- Merged: 2026-09-16T13:10:44Z
- Author: elezar
- Labels: none
- Associated issues: #2973 (open), #2974 (open), #2976 (open)
### What changed
This PR adds a portable `nextest` archive path for driver-agnostic OpenShell CLI smoke testing and executes that archive inside a provisioned `t-machine` guest. It adds a parameterized Nix archive builder for filtered `nextest` archives with workspace-remapping metadata, defines a standalone conformance CLI smoke-suite crate, includes its Linux archive in artifact builds, provisions `cargo-nextest` in `t-machine` guests, and runs the smoke archive after gateway installation.
### Larger task context
The PR body explicitly says it is stacked on #3371 and is related to #2973, #2974, and #2976 through #3371. It also states that it does not independently close an issue and is limited to a smoke-coverage test-infrastructure increment.

## PR #3371: test(tmachine): add portable VM-based container runtime testing
- URL: https://github.com/NVIDIA/OpenShell/pull/3371
- Merged: 2026-09-16T12:15:10Z
- Author: SDAChess
- Labels: none
- Associated issues: none identified
### What changed
This PR adds `tmachine`, a portable QEMU and Ansible test harness for validating OpenShell against real Linux guests. The harness covers Docker on Ubuntu plus rootful and rootless Podman on Fedora, and uses cached VM layers to speed up repeated runs.

Key changes include a Rust-based VM runner with separate setup, installation, and test phases; content-addressed QCOW2 layer caching; Linux and macOS provisioning for Ubuntu and Fedora cloud images across x86_64 and ARM64 hosts; Ansible playbooks for Docker, Podman, OpenShell gateway installation/configuration, and conformance smoke testing; Nix apps for artifacts; pinned macOS QEMU/OVMF runtime packages; failure logs/output; and documentation for the macOS QEMU and firmware package constraint.
### Larger task context
The PR explicitly links #2973, #2974, and #2976 and states that it establishes test infrastructure supporting planned Fedora rootless Podman and release qualification work. The linked issues are open and labeled around Linux/testing qualification: #2973 has `os:linux` and `topic:testing`; #2974 has `topic:testing`; #2976 has `os:linux`, `topic:testing`, and `state:stale`.

## Evidence Index

This index is rendered deterministically from GitHub API fields.

| Pull request | PR labels | Milestone | Associated issues | Related pull requests | Workstream labels |
|---|---|---|---|---|---|
| [#3334](https://github.com/NVIDIA/OpenShell/pull/3334) | `area:policy`, `test:e2e`, `topic:compatibility` | none | [#3333](https://github.com/NVIDIA/OpenShell/issues/3333) (closed; labels: `area:policy`, `test:e2e`, `topic:compatibility`) | none | `area:policy`, `topic:compatibility` |
| [#3354](https://github.com/NVIDIA/OpenShell/pull/3354) | none | none | none | none | none |
| [#3385](https://github.com/NVIDIA/OpenShell/pull/3385) | none | none | none | none | none |
| [#3372](https://github.com/NVIDIA/OpenShell/pull/3372) | none | none | [#2973](https://github.com/NVIDIA/OpenShell/issues/2973) (open; labels: `os:linux`, `topic:testing`); [#2974](https://github.com/NVIDIA/OpenShell/issues/2974) (open; labels: `topic:testing`); [#2976](https://github.com/NVIDIA/OpenShell/issues/2976) (open; labels: `os:linux`, `topic:testing`, `state:stale`) | none | none |
| [#3371](https://github.com/NVIDIA/OpenShell/pull/3371) | none | none | none | none | none |
