#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab4"
published_report=$(mktemp)
trap 'rm -f -- "$published_report"' EXIT

[[ $(nvidia-smi --query-gpu=name --format=csv,noheader | grep -c '^NVIDIA L40S$') -eq 4 ]]
systemctl --user is-active --quiet vllm.service
curl --silent --show-error --fail http://127.0.0.1:8000/v1/models \
    | grep -F 'Qwen/Qwen3.6-27B' >/dev/null
podman inspect vllm-qwen36 --format '{{json .Args}}' \
    | grep -F -- '--tensor-parallel-size' >/dev/null
grep -E '"tool_calls":[1-9][0-9]*' "$ROOT/evidence/gpu/agent-result.json" >/dev/null
if openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /sandbox/lab4-write-denied; then
    printf 'Lab 4 unexpectedly wrote outside approved paths\n' >&2
    exit 1
fi
if openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/curl --fail https://example.com/; then
    printf 'Lab 4 unexpectedly reached an unlisted host\n' >&2
    exit 1
fi
curl --silent --show-error --fail \
    http://127.0.0.1/openshell-lab/nvidia-openshell-last-5-merges.md \
    >"$published_report"
test -s "$published_report"
grep -F '# NVIDIA/OpenShell: Last 5 Merged Pull Requests' "$published_report" >/dev/null
openshell policy get "$SANDBOX" --full --output json \
    >"$ROOT/evidence/gpu/policy.json"
nvidia-smi --query-gpu=uuid,name,memory.total --format=csv,noheader \
    >"$ROOT/evidence/gpu/gpus.txt"
printf 'lab4 verification passed; Qwen and sandbox remain running\n'
