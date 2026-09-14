# Acceptance evidence index

| Requirement | Evidence |
|---|---|
| CPU RHEL/OpenShell health | `evidence/cpu/versions-and-platform.txt`, `evidence/cpu/service-states.txt` |
| Useful GPT-5.5 five-merge report | `evidence/cpu/nvidia-openshell-last-5-merges.md`, `evidence/cpu/report.sha256` |
| GitHub-only and filesystem controls | `evidence/cpu/effective-policies.jsonl`, `evidence/cpu/sandbox-logs.txt` |
| Lab 3 deny then allow | `evidence/cpu/lab3/policy-deny.json`, `evidence/cpu/lab3/policy-deny-probe.log`, `evidence/cpu/lab3/policy-allow.json`, `evidence/cpu/lab3/sandbox.log` |
| Lab 5 managed inference and health | `evidence/cpu/lab5/probe.json`, `evidence/cpu/lab5/health.txt` |
| Lab 5 Filesystem, Network, Process, and Provider controls | `evidence/cpu/lab5/policy.json`, `evidence/cpu/lab5/network-denial.log`, `evidence/cpu/lab5/process-status.txt`, `evidence/cpu/lab5/image-identity.txt` |
| Qwen tool-calling completion | `evidence/gpu/agent-result.json` records 10 tool calls |
| Four L40S GPUs (retained acceptance evidence) | `evidence/gpu/gpus.txt` |
| Lab 4 effective policy | `evidence/gpu/policy.json` |
| Exact behavior contract | `features/` and the unit tests under `tests/` |
| Editable workflow visual | `diagrams/openshell-ai-application-workflow.excalidraw` |
| Application security rationale | `docs/openshell-why-it-matters.md` |
| Secret hygiene | `scripts/scan-secrets.sh` and `.gitignore` |

Remote acceptance also fetched the reports through Apache from outside each
instance. Public addresses are mutable and are deliberately kept in the
gitignored `state/*-connection.env` files.

The CPU evidence was refreshed on 2026-09-14 with OpenShell v0.0.116. The
checked-in GPU evidence is retained from the earlier acceptance run. A
2026-09-14 capacity sweep found a four-L4 `g6.12xlarge` in `us-east-2a`; a live
feasibility run regenerated NVIDIA CDI, served Qwen3.6-27B at 32K with tensor
parallel 4 and a 16-sequence limit, and passed the Lab 4 security and report
checks on OpenShell v0.0.116. After that host was stopped, two guarded restart
attempts were rejected by EC2 with `InsufficientInstanceCapacity`; both GPU
instances remain stopped.
