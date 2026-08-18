#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab3"
REPORT="/var/www/html/openshell-lab/nvidia-openshell-last-5-merges.md"
IMAGE=$(awk -F= '$1 == "IMAGE" {print substr($0, index($0, "=") + 1)}' "$ROOT/state/lab3-image.env")

[[ $(podman image inspect "$IMAGE" --format '{{.Config.User}}') == "1500:1500" ]]
test -s "$REPORT"
grep -F '# NVIDIA/OpenShell: Last 5 Merged Pull Requests' "$REPORT" >/dev/null
grep -F 'api.github.com' "$ROOT/evidence/lab3/policy-allow.json" >/dev/null
if grep -F 'api.github.com' "$ROOT/evidence/lab3/policy-deny.json" >/dev/null; then
    printf 'deny policy evidence unexpectedly contains GitHub access\n' >&2
    exit 1
fi
curl --silent --show-error --fail-with-body \
    http://127.0.0.1/openshell-lab/nvidia-openshell-last-5-merges.md \
    | cmp - "$REPORT"
openshell logs "$SANDBOX" --source sandbox -n 500 \
    >"$ROOT/evidence/lab3/sandbox.log"
openshell sandbox delete "$SANDBOX" >/dev/null
test -s "$REPORT"
printf 'lab3 verification passed; report persisted after sandbox deletion\n'
