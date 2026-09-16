#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab4"
POLICY="$ROOT/policies/lab4-streamlit.yaml"
IMAGE_STATE="$ROOT/state/lab4-image.env"
FORWARD_UNIT="openshell-lab4-forward.service"
EVIDENCE_DIR="$ROOT/evidence/cpu/lab4"

[[ -r "$IMAGE_STATE" ]] || {
    printf 'Lab 4 image state is missing or unreadable; run build.sh first\n' >&2
    exit 1
}
IMAGE=$(awk -F= '$1 == "IMAGE" {print substr($0, index($0, "=") + 1)}' "$IMAGE_STATE")
[[ "$IMAGE" =~ ^localhost/openshell-lab-streamlit:[0-9a-f]{7,12}$ ]] || {
    printf 'Lab 4 image state is missing or invalid; run build.sh first\n' >&2
    exit 1
}

systemctl --user stop "$FORWARD_UNIT" >/dev/null 2>&1 || true
systemctl --user reset-failed "$FORWARD_UNIT" >/dev/null 2>&1 || true
forward_unit_loaded=true
for _ in $(seq 1 10); do
    load_state=$(
        systemctl --user show "$FORWARD_UNIT" \
            --property=LoadState --value 2>/dev/null || true
    )
    if [[ -z "$load_state" || "$load_state" == "not-found" ]]; then
        forward_unit_loaded=false
        break
    fi
    sleep 1
done
[[ "$forward_unit_loaded" == false ]] || {
    printf 'previous Lab 4 loopback forward service did not unload\n' >&2
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

mkdir -p "$EVIDENCE_DIR"
umask 077
CREATE_LOG="$EVIDENCE_DIR/sandbox-create.log"
if ! openshell sandbox create \
    --name "$SANDBOX" \
    --from "$IMAGE" \
    --policy "$POLICY" \
    --no-tty \
    -- /usr/bin/sleep infinity >/dev/null 2>"$CREATE_LOG"; then
    cat "$CREATE_LOG" >&2
    exit 1
fi

openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --workdir /opt/openshell-lab \
    --timeout 30 \
    -- /bin/sh -c \
    'nohup streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true </dev/null >/tmp/streamlit.log 2>&1 &'

internal_ready=false
for _ in $(seq 1 60); do
    if openshell sandbox exec \
        --name "$SANDBOX" \
        --no-tty \
        --timeout 10 \
        -- /usr/bin/curl --silent --fail --max-time 5 \
        http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1; then
        internal_ready=true
        break
    fi
    sleep 1
done
[[ "$internal_ready" == true ]] || {
    printf 'Lab 4 internal Streamlit health did not become ready\n' >&2
    exit 1
}

systemd-run --user --unit=openshell-lab4-forward --collect -- \
    openshell forward service openshell-lab4 \
    --target-port 8501 --local 127.0.0.1:18401 >/dev/null
systemctl --user is-active --quiet "$FORWARD_UNIT" || {
    printf 'Lab 4 loopback forward service is not active\n' >&2
    exit 1
}

host_ready=false
for _ in $(seq 1 30); do
    if curl --silent --fail --max-time 5 \
        http://127.0.0.1:18401/_stcore/health >/dev/null; then
        host_ready=true
        break
    fi
    sleep 1
done
[[ "$host_ready" == true ]] || {
    printf 'Lab 4 loopback Streamlit health did not become ready\n' >&2
    exit 1
}

printf 'lab4 Streamlit is ready on host loopback 127.0.0.1:18401\n'
