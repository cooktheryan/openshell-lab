# OpenShell five-lab workshop

This workshop demonstrates applications behind OpenShell across five
progressive labs. Labs 1–4 run on one CPU host: GitHub-only egress,
persistent-write confinement, deny/allow policy iteration, and a protected
Streamlit UI using managed GPT-5.5 inference. Lab 5 is an optional,
capacity-sensitive GPU exercise for local Qwen inference through vLLM. The
report agent retrieves the five latest merged NVIDIA/OpenShell pull requests,
inspects only explicitly linked issues, and publishes evidence-grounded
Markdown.

## Protection Layers

OpenShell applies defense in depth across four policy domains:

| Layer | What it protects | When it applies | Policy field |
|---|---|---|---|
| **Filesystem** | Prevents reads/writes outside allowed paths | Locked at sandbox creation | `filesystem_policy`, `landlock` |
| **Process** | Blocks privilege escalation and dangerous syscalls | Locked at sandbox creation | `process` |
| **Network** | Blocks unauthorized outbound connections | Hot-reloadable at runtime | `network_policies`, `network_middlewares` |
| **Providers** | Grants endpoint-bound credentials and network access | Hot-reloadable at runtime | Provider profiles + `credential_binding` |

See **`policies/openshell-four-layers.yaml`** for a complete policy demonstrating all four layers. See **`policies/minimal-network-only.yaml`** for a network-only policy.
The application-focused rationale is in
[Why OpenShell matters for AI applications](docs/openshell-why-it-matters.md).

## Live architecture

- Labs 1–4: RHEL 10 `t3.micro` in `us-east-1`, OpenShell RPM, rootless
  Podman, GPT-5.5 managed inference.
- Lab 5: RHEL 10.1 `g6.12xlarge` in `us-east-2`, four NVIDIA L4 GPUs,
  unquantized `Qwen/Qwen3.6-27B` BF16, vLLM 0.19.0, tensor parallel 4, 32K
  context, and an L4-safe 16-sequence concurrency limit. The vLLM scripts also
  support the validated four-L40S profile with a 256-sequence limit.
- Ordinary report-agent egress: read-only `api.github.com:443` by
  `/usr/bin/curl`; Lab 4 declares no ordinary egress.
- Model traffic: `https://inference.local/v1`, with provider credentials and
  upstream addresses held outside the agent.
- Publication: `/var/www/html` in the sandbox, an OpenShell loopback forward,
  and Apache on port 80.
- Streamlit: sandbox port 8501 forwarded only to CPU-host
  `127.0.0.1:18401`, then reached through SSH.

Open [the editable Excalidraw diagram](diagrams/openshell-ai-application-workflow.excalidraw)
or [the rendered SVG](diagrams/openshell-ai-application-workflow.svg).

## Prerequisites and cost

Install `aws`, `ssh`, `rsync`, `uv`, and optionally `shellcheck`. Configure AWS
credentials with permission to describe, start, stop, and launch the resources
in this repository. The private key is expected at `~/.ssh/id_rsa` and never
enters this repository.

Both instances are On-Demand and incur charges while running. The GPU host is
the dominant cost. Stop it with `./infra/aws/stop-gpu.sh` when the workshop is
finished; do not terminate it because its EBS volume contains the driver,
model, and compile caches.

## Labs 1–4: CPU host

Export the OpenAI key only in the launching terminal. The deployment streams
it over SSH standard input, configures the OpenShell provider, and unsets it.

```shell
export OPENAI_API_KEY='enter-the-value-interactively-here'
./scripts/deploy-cpu.sh
unset OPENAI_API_KEY
```

Connect without copying the key into project files:

```shell
source state/cpu-connection.env
ssh -i "$SSH_KEY_PATH" "$SSH_USER@$PUBLIC_IP"
```

On the host, the individual commands are:

```shell
cd ~/git/openshell-lab
./infra/remote/run-cpu-labs.sh
```

The sequence runner is equivalent to:

```shell
./labs/lab1/run.sh && ./labs/lab1/verify.sh
./labs/lab2/configure-host.sh
./labs/lab2/run.sh && ./labs/lab2/verify.sh
openshell forward stop 18080 openshell-lab2
./labs/lab3/build.sh
./labs/lab3/run.sh && ./labs/lab3/verify.sh
./labs/lab4/build.sh
./labs/lab4/run.sh && ./labs/lab4/verify.sh
```

Lab 1 verifies the proxy-enriched baseline Landlock ruleset plus three network
denials. Lab 2 persists only beneath `/var/www/html`; `/tmp` and `/dev/null`
remain bounded runtime paths. Lab 3 first blocks the agent with no network
capability, hot-loads the GitHub-read-only policy, then succeeds with the same
non-root image. Lab 2's forward is stopped before Lab 3 reuses loopback port
18080; Lab 3 remains forwarded for evidence collection.

Lab 4 reuses the Lab 1–3 `openai-gpt55` route but uses a separate
containerized Streamlit image and `openshell-lab4` sandbox. Its request goes
only to `inference.local`, with no credential, provider hostname, or model
selection in the application. Ordinary egress remains empty. Its durable
forward uses distinct host-loopback port 18401, so it does not disturb Lab 3.

Evidence-boundary violations from a model tool call remain denied, but the
agent returns sanitized retry guidance while the existing 16-call budget has
room. Reaching the limit still fails the run.

Install and use the simple home-directory runner:

```shell
./infra/remote/install-runner.sh
~/run-openshell-agent.sh lab3
~/run-openshell-agent.sh lab4
```

Discover the public report URL locally:

```shell
source state/cpu-connection.env
printf 'http://%s/openshell-lab/nvidia-openshell-last-5-merges.md\n' "$PUBLIC_IP"
```

## Lab 4: protected Streamlit on the CPU host

On the CPU host, build and start the application, then run the four-layer
acceptance verifier:

```shell
cd ~/git/openshell-lab
./labs/lab4/build.sh
./labs/lab4/run.sh
./labs/lab4/verify.sh
```

The verifier proves the **Filesystem**, **Network**, **Process**, and
**Provider** boundaries independently. It checks a successful model response
through `https://inference.local/v1/chat/completions`, a denied application-code
write, denied `example.com` egress with a matching audit event, hardened
process state, and absence of provider credential names from the workload.

From the local repository, open an SSH tunnel to the host's loopback-only
forward:

```shell
source state/cpu-connection.env
ssh -N -L 8501:127.0.0.1:18401 \
  -i "$SSH_KEY_PATH" \
  -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$PWD/state/known_hosts" \
  "$SSH_USER@$PUBLIC_IP"
```

Then browse to `http://127.0.0.1:8501`. Do not open port 18401 in the AWS
security group; the remote listener is intentionally loopback-only. See the
[Lab 4 runbook](labs/lab4/README.md) for evidence paths, expected denials,
inspection, and cleanup.

## Lab 5: Qwen/vLLM GPU host

The lifecycle script refuses to mutate any host that does not match the exact
instance type, AMI, key, security group, and owner/project/name tags.

The checked-in lifecycle now targets the stopped `g6.12xlarge` capacity host in
`us-east-2a`. The vLLM configuration regenerates NVIDIA CDI and rejects any GPU
layout other than four homogeneous L4 or four homogeneous L40S devices. This is
the workshop's expensive, optional exercise: capacity can be unavailable, and
the current Lab 5 remote acceptance remains pending until a guarded start and
verification succeed.

```shell
./infra/aws/start-gpu.sh
source state/gpu-connection.env
ssh -i "$SSH_KEY_PATH" "$SSH_USER@$PUBLIC_IP"
```

Upload this repository with the same exclusions used by `deploy-cpu.sh`, then
run the following primary sequence on the GPU host:

```shell
cd ~/git/openshell-lab
./infra/remote/bootstrap-rhel10.sh
./labs/lab2/configure-host.sh
./labs/lab5/configure-vllm.sh
./labs/lab5/configure-openshell.sh
./labs/lab5/run.sh
./labs/lab5/verify.sh
./infra/remote/install-runner.sh
```

## Optional vLLM monitoring (second terminal)

While the primary sequence continues in its first terminal, use a second
terminal to follow vLLM startup logs:

```shell
journalctl --user -u vllm.service -f
```

This command follows logs until you stop it with `Ctrl-C`; stopping the monitor
does not stop `vllm.service`.

The vLLM readiness check is:

```shell
curl --fail http://127.0.0.1:8000/v1/models
nvidia-smi
systemctl --user status vllm.service
```

`configure-openshell.sh` validates the loopback model endpoint, then configures
the injected `host.openshell.internal` alias with a non-secret compatibility
value. The sandbox continues to call only `inference.local`.

## Inspect OpenShell state and persistence

The bootstrap resolves NVIDIA/OpenShell's current stable GitHub release, fetches
that tag's installer, installs its checksum-verified RPM artifact, and refuses
to continue unless `openshell --version` matches the resolved tag. The latest
stable release verified during the 2026-09-14 CPU acceptance was
[`v0.0.116`](https://github.com/NVIDIA/OpenShell/releases/tag/v0.0.116); the
bootstrap resolves this dynamically rather than pinning that audit-time value.
Its user service unit is `/usr/lib/systemd/user/openshell-gateway.service`. Operator
configuration and gateway registration metadata persist under
`~/.config/openshell/`; local TLS and runtime state persist under
`~/.local/state/openshell/`. Provider secrets belong to OpenShell's provider
store and must never be copied into this repository.

Useful inspection commands:

```shell
openshell status
openshell sandbox list
openshell inference get
openshell provider get qwen36-local
openshell policy get openshell-lab5 --full --output json
openshell logs openshell-lab5 --source sandbox -n 200
systemctl --user status openshell-gateway
```

The policy files show the static controls. `lab3-network-deny.yaml` blocks
ordinary network egress while retaining the separately routed
`inference.local` service; `lab3-github-allow.yaml` additionally permits only
read-only GitHub API requests made by `/usr/bin/curl`.

## OpenShell container and policy model

The gateway is the local control plane and must be running before a sandbox can
be created. One gateway registers and manages multiple sandboxes. A sandbox may
use any compatible OCI image available to the configured Podman driver; the
image does not need to derive from an OpenShell base image.

OpenShell applies filesystem policy inside the running sandbox. It does not
rewrite the image's stored Unix modes. `read_only`, `read_write`, and
`include_workdir` determine the paths available to the sandbox process. A host
directory additionally requires a reviewed Podman bind mount, gateway setting
`enable_bind_mounts = true`, and a matching in-sandbox `read_write` path. The
Labs 2–3 and 5 mount is the worked example; Lab 4 needs no host bind mount.

Forwarded launchers save sandbox-creation diagnostics beneath `evidence/`
instead of leaving the background forward attached to an invoking SSH session.
This lets non-interactive deployment return while the forward remains active.
Lab 4 delegates its forward to `openshell-lab4-forward.service` and binds only
`127.0.0.1:18401`.

Network-policy `binaries` entries identify which executable may use a network
capability; they do not prohibit executing that binary. OpenShell v0.0.116 has
no `denied_executables` policy field. A tool such as `dnf` is therefore made
ineffective by denying its network destinations and keeping package-management
paths read-only, not by naming `dnf` in an executable deny list.

## Verification and review

```shell
./scripts/verify-all.sh
export OPENAI_API_KEY='review-only-value'
./review/run-ocr.sh
unset OPENAI_API_KEY
```

See [troubleshooting](docs/troubleshooting.md),
[why OpenShell matters](docs/openshell-why-it-matters.md), and the
[acceptance evidence index](docs/evidence-index.md). Neither script pushes a
branch or uploads credentials.

## Stop and restart

Stop the GPU host safely:

```shell
./infra/aws/stop-gpu.sh
```

Stop and restart the CPU host with the guarded lifecycle scripts:

```shell
./infra/aws/stop-cpu.sh
./infra/aws/start-cpu.sh
```

Before stopping the CPU host, Lab 4 can be removed independently:

```shell
systemctl --user stop openshell-lab4-forward.service
openshell sandbox delete openshell-lab4
```

The repository intentionally provides no termination command. The start script
refreshes the private state file and public address. User services use lingering
and resume automatically.

## OpenShell Pilot Proposal

A complete pilot proposal for presenting OpenShell to production teams is available at:
**[OpenShell Pilot Proposal](docs/superpowers/specs/openshell-pilot-proposal.md)**

The proposal covers:
- The security risk scenario (agent searching company resources with no boundaries)
- Why OpenShell instead of SELinux/Firewalld/containers alone
- All four protection layers with concrete examples
- The one-hour pilot plan on a single RHEL server
- Specific attack scenarios and how OpenShell stops each one

### Quick Pilot Start

```bash
# Install OpenShell
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh

# Build the agent container
podman build -t agent-policy-demo -f Containerfile .

# Create sandbox and apply policy
openshell sandbox create --name demo --from agent-policy-demo -- claude
openshell policy set demo --policy policies/openshell-four-layers.yaml --wait

# Verify each protection layer
openshell sandbox connect demo
```

See the pilot proposal for the full plan and attack scenarios.
