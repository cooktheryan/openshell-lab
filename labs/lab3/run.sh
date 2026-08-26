#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab3"
DENY_POLICY="$ROOT/policies/lab3-network-deny.yaml"
ALLOW_POLICY="$ROOT/policies/lab3-github-allow.yaml"
DRIVER_CONFIG='{"podman":{"mounts":[{"type":"bind","source":"/var/www/html/openshell-lab","target":"/var/www/html","read_only":false,"selinux_label":"private"}]}}'
IMAGE=$(awk -F= '$1 == "IMAGE" {print substr($0, index($0, "=") + 1)}' "$ROOT/state/lab3-image.env")
[[ "$IMAGE" =~ ^localhost/openshell-lab-agent:[0-9a-f]{7,12}$ ]] || {
    printf 'Lab 3 image state is missing or invalid; run build.sh first\n' >&2
    exit 1
}

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
podman unshare rm -f /var/www/html/openshell-lab/nvidia-openshell-last-5-merges.md
openshell forward stop 18080 openshell-lab3 >/dev/null 2>&1 || true

mkdir -p "$ROOT/evidence/lab3"
CREATE_LOG="$ROOT/evidence/lab3/sandbox-create.log"
if ! openshell sandbox create \
    --name "$SANDBOX" \
    --from "$IMAGE" \
    --policy "$DENY_POLICY" \
    --driver-config-json "$DRIVER_CONFIG" \
    --forward 127.0.0.1:18080 \
    --no-tty \
    -- /usr/bin/sleep infinity > /dev/null 2>"$CREATE_LOG"; then
    cat "$CREATE_LOG" >&2
    exit 1
fi

openshell policy get "$SANDBOX" --base --output json \
    >"$ROOT/evidence/lab3/policy-deny.json"
if openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --workdir /opt/openshell-lab \
    --timeout 900 \
    -- python3 -m openshell_lab.cli \
        --output /var/www/html/nvidia-openshell-last-5-merges.md; then
    printf 'expected denied report run to fail, but it succeeded\n' >&2
    exit 1
fi
printf 'expected denied report run was blocked\n'
podman unshare rm -f /var/www/html/openshell-lab/nvidia-openshell-last-5-merges.md

openshell policy set "$SANDBOX" --policy "$ALLOW_POLICY" --wait --timeout 120
openshell policy get "$SANDBOX" --base --output json \
    >"$ROOT/evidence/lab3/policy-allow.json"
openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --workdir /opt/openshell-lab \
    --timeout 900 \
    -- python3 -m openshell_lab.cli \
        --output /var/www/html/nvidia-openshell-last-5-merges.md
openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /var/www/html/empty-input
openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /bin/sh -c 'nohup python3 -m http.server 18080 --bind 0.0.0.0 --directory /var/www/html </var/www/html/empty-input >/var/www/html/http-server.log 2>&1 &'
for _ in $(seq 1 30); do
    if curl --silent --fail http://127.0.0.1:18080/nvidia-openshell-last-5-merges.md >/dev/null; then
        printf 'lab3 deny-then-allow run passed\n'
        exit 0
    fi
    sleep 1
done
printf 'Lab 3 report service did not become ready\n' >&2
exit 1
