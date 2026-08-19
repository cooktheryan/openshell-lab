# OpenShell four-lab workshop

This workshop demonstrates one report agent behind OpenShell across four
incremental controls: GitHub-only egress, persistent-write confinement,
deny/allow policy iteration, and local Qwen inference through vLLM. The agent
retrieves the five latest merged NVIDIA/OpenShell pull requests, inspects only
explicitly linked issues, and publishes evidence-grounded Markdown.

## Live architecture

- Labs 1–3: RHEL 10 `t3.micro` in `us-east-1`, OpenShell RPM, rootless Podman,
  GPT-5.5 managed inference.
- Lab 4: RHEL 10.1 `g6e.12xlarge` in `us-east-2`, four NVIDIA L40S GPUs,
  unquantized `Qwen/Qwen3.6-27B` BF16, vLLM 0.19.0, tensor parallel 4, 32K
  context.
- Ordinary sandbox egress: read-only `api.github.com:443` by `/usr/bin/curl`.
- Model traffic: `https://inference.local/v1`, with provider credentials and
  upstream addresses held outside the agent.
- Publication: `/var/www/html` in the sandbox, an OpenShell loopback forward,
  and Apache on port 80.

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

## Labs 1–3: CPU host

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
./labs/lab1/run.sh && ./labs/lab1/verify.sh
./labs/lab2/configure-host.sh
./labs/lab2/run.sh && ./labs/lab2/verify.sh
./labs/lab3/build.sh
./labs/lab3/run.sh && ./labs/lab3/verify.sh
```

Lab 1 verifies the proxy-enriched baseline Landlock ruleset plus three network
denials. Lab 2 persists only beneath `/var/www/html`; `/tmp` and `/dev/null`
remain bounded runtime paths. Lab 3 first blocks the agent with no network
capability, hot-loads the GitHub-read-only policy, then succeeds with the same
non-root image.

Install and use the simple home-directory runner:

```shell
./infra/remote/install-runner.sh
~/run-openshell-agent.sh lab3
```

Discover the public report URL locally:

```shell
source state/cpu-connection.env
printf 'http://%s/openshell-lab/nvidia-openshell-last-5-merges.md\n' "$PUBLIC_IP"
```

## Lab 4: Qwen/vLLM GPU host

The lifecycle script refuses to mutate any host that does not match the exact
instance type, AMI, key, security group, and owner/project/name tags.

```shell
./infra/aws/start-gpu.sh
source state/gpu-connection.env
ssh -i "$SSH_KEY_PATH" "$SSH_USER@$PUBLIC_IP"
```

Upload this repository with the same exclusions used by `deploy-cpu.sh`, then
run on the GPU host:

```shell
cd ~/git/openshell-lab
./infra/remote/bootstrap-rhel10.sh
./labs/lab2/configure-host.sh
./labs/lab4/configure-vllm.sh
journalctl --user -u vllm.service -f
./labs/lab4/configure-openshell.sh
./labs/lab4/run.sh
./labs/lab4/verify.sh
./infra/remote/install-runner.sh
```

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
stable release verified during the 2026-08-18 review was
[`v0.0.106`](https://github.com/NVIDIA/OpenShell/releases/tag/v0.0.106); the
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
openshell policy get openshell-lab4 --full --output json
openshell logs openshell-lab4 --source sandbox -n 200
systemctl --user status openshell-gateway
```

The policy files show the static controls. `lab3-network-deny.yaml` stops the
agent entirely; `lab3-github-allow.yaml` permits only GitHub reads by curl.

## Verification and review

```shell
./scripts/verify-all.sh
export OPENAI_API_KEY='review-only-value'
./review/run-ocr.sh
unset OPENAI_API_KEY
```

See [troubleshooting](docs/troubleshooting.md) and the
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

The repository intentionally provides no termination command. The start script
refreshes the private state file and public address. User services use lingering
and resume automatically.
