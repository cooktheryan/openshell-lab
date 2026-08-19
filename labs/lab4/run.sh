#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab4"
IMAGE="localhost/openshell-lab-agent:lab4"
POLICY="$ROOT/policies/lab3-github-allow.yaml"
DRIVER_CONFIG='{"podman":{"mounts":[{"type":"bind","source":"/var/www/html/openshell-lab","target":"/var/www/html","read_only":false,"selinux_label":"private"}]}}'

podman build --tag "$IMAGE" --file "$ROOT/container/Containerfile" "$ROOT" >/dev/null
[[ $(podman image inspect "$IMAGE" --format '{{.Config.User}}') == "1500:1500" ]]
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
openshell forward stop 18080 openshell-lab3 >/dev/null 2>&1 || true
podman unshare rm -f /var/www/html/openshell-lab/nvidia-openshell-last-5-merges.md

openshell sandbox create --name "$SANDBOX" --from "$IMAGE" \
    --policy "$POLICY" --driver-config-json "$DRIVER_CONFIG" \
    --forward 127.0.0.1:18080 --no-tty -- /bin/true >/dev/null
mkdir -p "$ROOT/evidence/gpu"
openshell sandbox exec --name "$SANDBOX" --no-tty \
    --workdir /opt/openshell-lab --timeout 1800 -- \
    python3 -m openshell_lab.cli \
        --output /var/www/html/nvidia-openshell-last-5-merges.md \
    | tee "$ROOT/evidence/gpu/agent-result.json"
openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /var/www/html/empty-input
openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /bin/sh -c 'nohup python3 -m http.server 18080 --bind 0.0.0.0 --directory /var/www/html </var/www/html/empty-input >/var/www/html/http-server.log 2>&1 &'
for _ in $(seq 1 30); do
    if curl --silent --fail http://127.0.0.1:18080/nvidia-openshell-last-5-merges.md >/dev/null; then
        printf 'lab4 report service is ready\n'
        exit 0
    fi
    sleep 1
done
printf 'Lab 4 report service did not become ready\n' >&2
exit 1
