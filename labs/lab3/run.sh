#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab3"
DENY_POLICY="$ROOT/policies/lab3-network-deny.yaml"
ALLOW_POLICY="$ROOT/policies/lab3-github-allow.yaml"
REPORT_HOST_PATH="/var/www/html/openshell-lab/nvidia-openshell-last-5-merges.md"
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
podman unshare rm -f "$REPORT_HOST_PATH"
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
probe_status=0
if openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 30 \
    -- /usr/bin/curl \
        --silent \
        --show-error \
        --fail \
        --max-time 20 \
        --output /dev/null \
        https://api.github.com/rate_limit; then
    printf 'expected denied GitHub probe to fail, but it succeeded\n' >&2
    exit 1
else
    probe_status=$?
fi
DENY_LOG="$ROOT/evidence/lab3/policy-deny-probe.log"
denial_verified=false
denial_wait=30
while ((denial_wait > 0)); do
    if ! openshell logs "$SANDBOX" --source sandbox -n 200 >"$DENY_LOG"; then
        printf 'failed to retrieve Lab 3 denial audit events\n' >&2
        exit 1
    fi
    if grep -Eq \
        'NET:OPEN.*DENIED /usr/bin/curl\([0-9]+\) -> api\.github\.com:443' \
        "$DENY_LOG"; then
        denial_verified=true
        break
    fi
    ((denial_wait--))
    ((denial_wait == 0)) || sleep 1
done
if [[ "$denial_verified" != true ]]; then
    printf 'GitHub probe failed with status %s without a policy-denial audit event\n' \
        "$probe_status" >&2
    exit 1
fi
printf 'expected denied GitHub probe was blocked by policy\n'
report_check_status=0
if podman unshare test -e "$REPORT_HOST_PATH"; then
    report_check_status=0
else
    report_check_status=$?
fi
case "$report_check_status" in
    0)
        printf 'denied GitHub probe unexpectedly produced a report\n' >&2
        exit 1
        ;;
    1)
        printf 'denied GitHub probe produced no report\n'
        ;;
    *)
        printf 'failed to check for a denied-phase report (status %s)\n' \
            "$report_check_status" >&2
        exit 1
        ;;
esac

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
