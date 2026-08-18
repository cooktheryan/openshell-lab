#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab2"
POLICY="$ROOT/policies/lab2-webroot-only.yaml"
DRIVER_CONFIG='{"podman":{"mounts":[{"type":"bind","source":"/var/www/html/openshell-lab","target":"/var/www/html","read_only":false,"selinux_label":"private"}]}}'

if openshell sandbox list --names | grep -Fx "$SANDBOX" >/dev/null; then
    openshell sandbox delete "$SANDBOX" >/dev/null
fi

openshell sandbox create \
    --name "$SANDBOX" \
    --policy "$POLICY" \
    --driver-config-json "$DRIVER_CONFIG" \
    --upload "$ROOT/src:/opt/openshell-lab" \
    --forward 127.0.0.1:18080 \
    --no-tty \
    -- /bin/true >/dev/null

openshell sandbox exec \
    --name "$SANDBOX" \
    --workdir /opt/openshell-lab \
    --env PYTHONPATH=/opt/openshell-lab/src \
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
