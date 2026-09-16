# Acceptance evidence index

| Requirement | Evidence |
|---|---|
| CPU RHEL/OpenShell health | `evidence/cpu/versions-and-platform.txt`, `evidence/cpu/service-states.txt` |
| Useful GPT-5.5 five-merge report | `evidence/cpu/nvidia-openshell-last-5-merges.md`, `evidence/cpu/report.sha256` |
| GitHub-only and filesystem controls | `evidence/cpu/effective-policies.jsonl`, `evidence/cpu/sandbox-logs.txt` |
| Lab 3 deny then allow | `evidence/cpu/lab3/policy-deny.json`, `evidence/cpu/lab3/policy-deny-probe.log`, `evidence/cpu/lab3/policy-allow.json`, `evidence/cpu/lab3/sandbox.log` |
| Lab 4 managed inference and health (pending CPU acceptance) | Expected at `evidence/cpu/lab4/probe.json`, `evidence/cpu/lab4/health.txt` after successful Task 7 acceptance |
| Lab 4 Filesystem, Network, Process, and Provider controls (pending CPU acceptance) | Expected at `evidence/cpu/lab4/policy.json`, `evidence/cpu/lab4/network-denial.log`, `evidence/cpu/lab4/process-status.txt`, `evidence/cpu/lab4/image-identity.txt` after successful Task 7 acceptance |
| Lab 5 Qwen tool-calling and effective policy (pending GPU capacity) | Expected at `evidence/gpu/agent-result.json`, `evidence/gpu/gpus.txt`, and `evidence/gpu/policy.json` only after successful Task 8 acceptance |
| Exact behavior contract | `features/` and the unit tests under `tests/` |
| Editable workflow visual | `diagrams/openshell-ai-application-workflow.excalidraw` |
| Application security rationale | `docs/openshell-why-it-matters.md` |
| Secret hygiene | `scripts/scan-secrets.sh` and `.gitignore` |

Remote acceptance also fetched the reports through Apache from outside each
instance. Public addresses are mutable and are deliberately kept in the
gitignored `state/*-connection.env` files.

Labs 1–3 retain their CPU evidence. There is no current Lab 4 CPU acceptance
evidence: it is created only by a successful Task 7 run and is stored beneath
`evidence/cpu/lab4/`. There is no current Lab 5 GPU acceptance evidence:
`evidence/gpu/` becomes current only after successful Task 8 acceptance. The
guarded GPU start may fail with `InsufficientInstanceCapacity`; in that case,
Lab 5 remote validation remains pending capacity and does not authorize a
replacement host or instance type.
