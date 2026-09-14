#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab2"
POLICY="$ROOT/policies/lab2-webroot-only.yaml"
DRIVER_CONFIG='{"podman":{"mounts":[{"type":"bind","source":"/var/www/html/openshell-lab","target":"/var/www/html","read_only":false,"selinux_label":"private"}]}}'
IMAGE="localhost/openshell-lab-agent:lab2"

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

mkdir -p "$ROOT/evidence/lab2"
CREATE_LOG="$ROOT/evidence/lab2/sandbox-create.log"
if ! openshell sandbox create \
    --name "$SANDBOX" \
    --from "$IMAGE" \
    --policy "$POLICY" \
    --driver-config-json "$DRIVER_CONFIG" \
    --forward 127.0.0.1:18080 \
    --no-tty \
    -- /usr/bin/sleep infinity > /dev/null 2>"$CREATE_LOG"; then
    cat "$CREATE_LOG" >&2
    exit 1
fi

openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --workdir /opt/openshell-lab \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --timeout 900 \
    -- python3 -m openshell_lab.cli \
        --output /var/www/html/nvidia-openshell-last-5-merges.md

openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /var/www/html/empty-input
openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /bin/sh -c 'nohup python3 -m http.server 18080 --bind 0.0.0.0 --directory /var/www/html </var/www/html/empty-input >/var/www/html/http-server.log 2>&1 &'

for _ in $(seq 1 30); do
    if curl --silent --fail http://127.0.0.1:18080/nvidia-openshell-last-5-merges.md >/dev/null; then
        printf 'report_url=http://127.0.0.1/openshell-lab/nvidia-openshell-last-5-merges.md\n'
        exit 0
    fi
    sleep 1
done
printf 'sandbox report service did not become ready\n' >&2
exit 1
