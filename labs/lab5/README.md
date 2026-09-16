# Lab 5: local Qwen through vLLM and OpenShell

This lab runs unquantized `Qwen/Qwen3.6-27B` in BF16 across exactly four
homogeneous NVIDIA GPUs. The guarded host is a `g6.12xlarge` with four L4 GPUs;
the scripts also retain the validated four-L40S `g6e.12xlarge` profile. vLLM
serves a 32,768-token OpenAI-compatible endpoint with Qwen reasoning and
tool-call parsers. OpenShell
maps the injected `host.openshell.internal` endpoint to `inference.local`, so
the application code and its credential-free model request do not change. The
configuration script first validates the model locally, then skips gateway-side
verification because the alias exists only at the sandbox boundary.

The configuration regenerates NVIDIA CDI before starting vLLM. It limits L4
hosts to 16 concurrent sequences to leave warm-up headroom, while L40S hosts
use 256. Mixed GPU models, unsupported models, and any count other than four
are rejected before the service is changed.

Lab 5 is optional, expensive, and capacity-sensitive. Do not treat a prior
acceptance record as current evidence: GPU evidence becomes current only after
the guarded host starts and this Lab 5 verification succeeds.

On the GPU host, run the following primary sequence:

If this host previously ran the pre-renumbering GPU exercise, perform this
one-time cleanup before starting Lab 5:

```shell
openshell forward stop 18080 openshell-lab4
openshell sandbox delete openshell-lab4
```

The current Lab 5 launcher owns only `openshell-lab5`; these explicit commands
avoid deleting a different lab during normal launches.

```shell
./labs/lab5/configure-vllm.sh
./labs/lab5/configure-openshell.sh
./labs/lab2/configure-host.sh
./labs/lab5/run.sh
./labs/lab5/verify.sh
```

## Optional vLLM monitoring (second terminal)

While the primary sequence continues in its first terminal, use a second
terminal to follow vLLM startup logs:

```shell
journalctl --user -u vllm.service -f
```

This command follows logs until you stop it with `Ctrl-C`; stopping the monitor
does not stop `vllm.service`.

The first vLLM start downloads roughly the BF16 model weight size and may take
several minutes. The vLLM service, OpenShell sandbox, Apache report endpoint,
and EC2 instance remain running after verification.

Sandbox-creation diagnostics are retained in
`evidence/gpu/sandbox-create.log`, independently of the SSH session that starts
the lab. After a successful verification, the GPU evidence collector replaces
`evidence/gpu/`; until then, Lab 5 remote acceptance is pending capacity.
