#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab3"
IMAGE=$(awk -F= '$1 == "IMAGE" {print substr($0, index($0, "=") + 1)}' "$ROOT/state/lab3-image.env")
published_report=$(mktemp)
trap 'rm -f -- "$published_report"' EXIT

[[ $(podman image inspect "$IMAGE" --format '{{.Config.User}}') == "1500:1500" ]]
grep -F 'api.github.com' "$ROOT/evidence/lab3/policy-allow.json" >/dev/null
if grep -F 'api.github.com' "$ROOT/evidence/lab3/policy-deny.json" >/dev/null; then
    printf 'deny policy evidence unexpectedly contains GitHub access\n' >&2
    exit 1
fi
curl --silent --show-error --fail-with-body \
    http://127.0.0.1/openshell-lab/nvidia-openshell-last-5-merges.md \
    >"$published_report"
test -s "$published_report"
grep -F '# NVIDIA/OpenShell: Last 5 Merged Pull Requests' "$published_report" >/dev/null
openshell logs "$SANDBOX" --source sandbox -n 500 \
    >"$ROOT/evidence/lab3/sandbox.log"
printf 'lab3 verification passed; sandbox and report service remain running\n'
