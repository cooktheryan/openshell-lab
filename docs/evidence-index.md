# Acceptance evidence index

| Requirement | Evidence |
|---|---|
| CPU RHEL/OpenShell health | `evidence/cpu/versions-and-platform.txt`, `evidence/cpu/service-states.txt` |
| Useful GPT-5.5 five-merge report | `evidence/cpu/nvidia-openshell-last-5-merges.md`, `evidence/cpu/report.sha256` |
| GitHub-only and filesystem controls | `evidence/cpu/effective-policies.jsonl`, `evidence/cpu/sandbox-logs.txt` |
| Lab 3 deny then allow | `evidence/cpu/lab3/policy-deny.json`, `evidence/cpu/lab3/policy-deny-probe.log`, `evidence/cpu/lab3/policy-allow.json`, `evidence/cpu/lab3/sandbox.log` |
| Qwen tool-calling completion | `evidence/gpu/agent-result.json` records 10 tool calls |
| Four L40S GPUs | `evidence/gpu/gpus.txt` |
| Lab 4 effective policy | `evidence/gpu/policy.json` |
| Exact behavior contract | `features/` and the unit tests under `tests/` |
| Editable workflow visual | `diagrams/openshell-ai-application-workflow.excalidraw` |
| Secret hygiene | `scripts/scan-secrets.sh` and `.gitignore` |

Remote acceptance also fetched the reports through Apache from outside each
instance. Public addresses are mutable and are deliberately kept in the
gitignored `state/*-connection.env` files.

The CPU evidence was refreshed on 2026-09-14 with OpenShell v0.0.116. The GPU
evidence is retained from the earlier acceptance run; three guarded attempts to
restart the existing g6e.12xlarge for a v0.0.113 refresh were rejected by EC2
with `InsufficientInstanceCapacity`, and the instance remained stopped.
