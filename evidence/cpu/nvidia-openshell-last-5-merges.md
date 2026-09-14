# NVIDIA/OpenShell: Last 5 Merged Pull Requests
## Executive Summary
The five latest merged pull requests all landed on 2026-09-14 and were authored by drew. They form an RFC 0012 isolation stack across multiple execution drivers, followed by benchmark coverage for the resulting TCP and DNS mediation paths. Each PR is labeled `test:e2e` and explicitly states it is part of issue #1737, "feat: establish the Isolation Backend interface," which remains open and carries the labels `area:sandbox` and `rfc`. The implementation PRs move workload network access behind an authenticated supervisor/sandbox split for VM, Docker, Kubernetes, and Podman; the most recent PR adds measurement-only performance harnesses for that stack.

## PR #3229: perf(isolation): add TCP and DNS benchmark harnesses
- URL: https://github.com/NVIDIA/OpenShell/pull/3229
- Merged: 2026-09-14T20:10:17Z
- Author: drew
- Labels: test:e2e
- Associated issues: #1737 (open)
### What changed
This PR adds benchmark harnesses for the RFC 0012 stack. The PR body says the harnesses separately measure startup, DNS, new TCP connections, reused TCP streams, policy denial, and representative live-Internet workloads. It adds a native-versus-filtered TCP microbenchmark, measures intercepted connection setup and the established-stream fast path, adds live-Internet and end-to-end network scenarios, keeps benchmark code behind the `perf-harness` feature and outside production paths, and improves setup-failure handling by canceling prepared workers promptly when another worker fails setup. The PR describes this as measurement-only work and notes that general application UDP remains out of scope, while DNS keeps normal UDP/TCP behavior through supervisor mediation.
### Larger task context
The PR body explicitly says it is "Part of #1737." Issue #1737 is titled "feat: establish the Isolation Backend interface" and is labeled `area:sandbox` and `rfc`. The PR body also includes a stack list identifying this as the performance-harness step after RFC 0012 core architecture and the VM, Docker, Kubernetes, and Podman driver work.

## PR #3230: feat(podman): isolate workloads behind a separate supervisor
- URL: https://github.com/NVIDIA/OpenShell/pull/3230
- Merged: 2026-09-14T20:10:16Z
- Author: drew
- Labels: test:e2e
- Associated issues: #1737 (open)
### What changed
This PR adds the Podman implementation of RFC 0012. The driver launches separate workload and supervisor containers, connects them through a private Unix socket, and denies direct workload egress. The OpenShell Sandbox Protocol uses a pinned TLS server identity and launch-scoped sandbox JWT over that socket. The implementation provisions the workload, supervisor, Unix socket, bootstrap material, and outer fence; keeps supervisor tokens, client TLS material, and proxy credentials out of the workload container; preserves template and request environment variables while protecting `OPENSHELL_*` control values; applies native OCI PID and AppArmor settings; and rotates generation and authentication material on restart.
### Larger task context
The PR body explicitly says it is "Part of #1737." Issue #1737 is titled "feat: establish the Isolation Backend interface" and is labeled `area:sandbox` and `rfc`. The PR body also places this Podman driver work in an RFC 0012 stack after core architecture, VM, Docker, and Kubernetes work, and before performance harnesses.

## PR #3144: feat(kubernetes): isolate workloads behind a dedicated supervisor
- URL: https://github.com/NVIDIA/OpenShell/pull/3144
- Merged: 2026-09-14T20:10:14Z
- Author: drew
- Labels: test:e2e
- Associated issues: #1737 (open)
### What changed
This PR adds the Kubernetes implementation of RFC 0012. The workload Pod runs `openshell-sandbox`, while a directly managed supervisor Pod runs `openshell-supervisor`. The driver denies direct workload egress and preserves supervisor egress with two shared namespace NetworkPolicies. The PR renders separate workload and supervisor Pods, gates both Pods until immutable bootstrap material and network fences are ready, denies workload-initiated egress with a namespace-wide policy, allows egress for OpenShell supervisor-role Pods with a second namespace-wide policy, splits Secrets so workloads receive only TLS server material and public JWT verification keys, gives the supervisor its gateway token, sandbox token, and pinned sandbox CA, rotates session/token/TLS/Pod/Secret state on restart, and reconciles Services, Secrets, workloads, supervisors, and shared NetworkPolicies together.
### Larger task context
The PR body explicitly says it is "Part of #1737." Issue #1737 is titled "feat: establish the Isolation Backend interface" and is labeled `area:sandbox` and `rfc`. The PR body also places this Kubernetes driver work in an RFC 0012 stack after core architecture, VM, and Docker work, and before Podman and performance-harness work.

## PR #2965: feat(docker): isolate workloads behind a companion supervisor
- URL: https://github.com/NVIDIA/OpenShell/pull/2965
- Merged: 2026-09-14T20:10:13Z
- Author: drew
- Labels: test:e2e
- Associated issues: #1737 (open)
### What changed
This PR adopts RFC 0012 in the Docker driver. The workload container runs `openshell-sandbox` with Docker networking disabled, while a companion `openshell-supervisor` container owns policy and mediated TCP/DNS access. The driver provisions a private Unix socket between containers and authenticates the OpenShell Sandbox Protocol with a pinned TLS server identity and launch-scoped sandbox JWT. The changes include launching workloads with `network_mode=none`, launching the supervisor on the Docker host network, keeping supervisor credentials/client TLS/proxy credentials out of the workload container, preserving a running workload during gateway recovery by replacing only its supervisor session, adopting missing generation markers for older running sandboxes and rejecting conflicting generations, failing closed when the supervisor or protected channel is unavailable, and preserving the accepted schema-v2 Docker configuration plus typed image-pull policy.
### Larger task context
The PR body explicitly says it is "Part of #1737." Issue #1737 is titled "feat: establish the Isolation Backend interface" and is labeled `area:sandbox` and `rfc`. The PR body also places this Docker driver work in an RFC 0012 stack after core architecture and VM work, and before Kubernetes, Podman, and performance-harness work.

## PR #2945: feat(vm): run the supervisor outside the guest workload
- URL: https://github.com/NVIDIA/OpenShell/pull/2945
- Merged: 2026-09-14T20:10:11Z
- Author: drew
- Labels: test:e2e
- Associated issues: #1737 (open)
### What changed
This PR adopts the RFC 0012 split in the VM driver. `openshell-supervisor` runs on the host, while `openshell-sandbox` runs as guest init and owns the agent process tree. The private guest channel uses the same pinned TLS server identity and launch-scoped sandbox JWT used by the other drivers, carried over vsock or the hypervisor Unix-socket mapping. The PR boots the guest with the sandbox runtime, TLS server material, and public JWT verification keys; keeps supervisor JWTs and the pinned sandbox CA on the host; runs the external host supervisor with durable runtime state; removes the guest NIC, TAP, gvproxy, nftables, and direct guest egress path; carries lifecycle, process control, TCP, and DNS over the authenticated Sandbox Protocol; and keeps gateway, provider, and upstream network access outside the guest.
### Larger task context
The PR body explicitly says it is "Part of #1737." Issue #1737 is titled "feat: establish the Isolation Backend interface" and is labeled `area:sandbox` and `rfc`. The PR body also places this VM driver work in an RFC 0012 stack after core architecture and before Docker, Kubernetes, Podman, and performance-harness work.

## Evidence Index

This index is rendered deterministically from GitHub API fields.

| Pull request | PR labels | Milestone | Associated issues | Related pull requests | Workstream labels |
|---|---|---|---|---|---|
| [#3229](https://github.com/NVIDIA/OpenShell/pull/3229) | `test:e2e` | none | [#1737](https://github.com/NVIDIA/OpenShell/issues/1737) (open; labels: `area:sandbox`, `rfc`) | none | none |
| [#3230](https://github.com/NVIDIA/OpenShell/pull/3230) | `test:e2e` | none | [#1737](https://github.com/NVIDIA/OpenShell/issues/1737) (open; labels: `area:sandbox`, `rfc`) | none | none |
| [#3144](https://github.com/NVIDIA/OpenShell/pull/3144) | `test:e2e` | none | [#1737](https://github.com/NVIDIA/OpenShell/issues/1737) (open; labels: `area:sandbox`, `rfc`) | none | none |
| [#2965](https://github.com/NVIDIA/OpenShell/pull/2965) | `test:e2e` | none | [#1737](https://github.com/NVIDIA/OpenShell/issues/1737) (open; labels: `area:sandbox`, `rfc`) | none | none |
| [#2945](https://github.com/NVIDIA/OpenShell/pull/2945) | `test:e2e` | none | [#1737](https://github.com/NVIDIA/OpenShell/issues/1737) (open; labels: `area:sandbox`, `rfc`) | none | none |
