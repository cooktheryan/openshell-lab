# Lab 4: local Qwen through vLLM and OpenShell

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

On the GPU host, run:

```shell
./labs/lab4/configure-vllm.sh
journalctl --user -u vllm.service -f
./labs/lab4/configure-openshell.sh
./labs/lab2/configure-host.sh
./labs/lab4/run.sh
./labs/lab4/verify.sh
```

The first vLLM start downloads roughly the BF16 model weight size and may take
several minutes. The vLLM service, OpenShell sandbox, Apache report endpoint,
and EC2 instance remain running after verification.

Sandbox-creation diagnostics are retained in
`evidence/gpu/sandbox-create.log`, independently of the SSH session that starts
the lab.
