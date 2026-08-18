#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab1"
POLICY="$ROOT/policies/lab1-github-only-baseline-filesystem.yaml"
EVIDENCE_DIR="$ROOT/evidence/lab1"
REPORT="$EVIDENCE_DIR/nvidia-openshell-last-5-merges.md"

if openshell sandbox list --names | grep -Fx "$SANDBOX" >/dev/null; then
    openshell sandbox delete "$SANDBOX" >/dev/null
fi
delete_wait=60
while openshell sandbox list --names | grep -Fx "$SANDBOX" >/dev/null; do
    ((delete_wait--)) || {
        printf 'sandbox deletion timed out: %s\n' "$SANDBOX" >&2
        exit 1
    }
    sleep 1
done

openshell sandbox create \
    --name "$SANDBOX" \
    --policy "$POLICY" \
    --upload "$ROOT/src:/sandbox" \
    --no-tty \
    -- /bin/true >/dev/null

openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --workdir /sandbox \
    --env PYTHONPATH=/sandbox/src \
    --timeout 900 \
    -- python3 -m openshell_lab.cli \
        --output /sandbox/nvidia-openshell-last-5-merges.md

mkdir -p "$EVIDENCE_DIR"
openshell sandbox download \
    "$SANDBOX" \
    /sandbox/nvidia-openshell-last-5-merges.md \
    "$REPORT"
printf 'report=%s\n' "$REPORT"
