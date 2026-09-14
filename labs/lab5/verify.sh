#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab5"
IMAGE_STATE="$ROOT/state/lab5-image.env"
FORWARD_UNIT="openshell-lab5-forward.service"
EVIDENCE_DIR="$ROOT/evidence/cpu/lab5"

[[ -r "$IMAGE_STATE" ]] || {
    printf 'Lab 5 image state is missing or unreadable\n' >&2
    exit 1
}
IMAGE=$(awk -F= '$1 == "IMAGE" {print substr($0, index($0, "=") + 1)}' "$IMAGE_STATE")
[[ "$IMAGE" =~ ^localhost/openshell-lab-streamlit:[0-9a-f]{7,12}$ ]] || {
    printf 'Lab 5 image state is invalid\n' >&2
    exit 1
}

mkdir -p "$EVIDENCE_DIR"
umask 077

identity=$(podman image inspect "$IMAGE" --format '{{.Config.User}}')
[[ "$identity" == "1500:1500" ]] || {
    printf 'Lab 5 image identity is not 1500:1500\n' >&2
    exit 1
}
printf '%s\n' "$identity" >"$EVIDENCE_DIR/image-identity.txt"

systemctl --user is-active --quiet "$FORWARD_UNIT" || {
    printf 'Lab 5 loopback forward service is not active\n' >&2
    exit 1
}
curl --silent --show-error --fail --max-time 10 \
    http://127.0.0.1:18501/_stcore/health \
    >"$EVIDENCE_DIR/health.txt"
test -s "$EVIDENCE_DIR/health.txt"

POLICY_EVIDENCE="$EVIDENCE_DIR/policy.json"
openshell policy get "$SANDBOX" --full --output json >"$POLICY_EVIDENCE"
python3 - "$POLICY_EVIDENCE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    document = json.load(stream)
policy = document["policy"]
assert document["status"] == "effective"
assert policy["landlock"]["compatibility"] == "hard_requirement"
assert policy["network_policies"] == {}
assert policy["process"]["run_as_user"] == "1500"
assert policy["process"]["run_as_group"] == "1500"
assert policy["filesystem_policy"]["read_write"] == ["/tmp", "/dev/null"]
assert "/opt/openshell-lab" in policy["filesystem_policy"]["read_only"]
PY

openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --workdir /opt/openshell-lab \
    --timeout 240 \
    -- python3 probe.py >"$EVIDENCE_DIR/probe.json"
python3 - "$EVIDENCE_DIR/probe.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    result = json.load(stream)
assert set(result) == {"status", "response"}
assert result["status"] == "ok"
assert isinstance(result["response"], str) and result["response"].strip()
PY

if openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- /usr/bin/touch /opt/openshell-lab/lab5-write-denied \
    >/dev/null 2>&1; then
    printf 'Lab 5 application directory accepted a write\n' >&2
    exit 1
fi

network_status=0
if openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 20 \
    -- python3 -c \
    'import httpx; response = httpx.get("https://example.com", timeout=10); response.raise_for_status()' \
    >/dev/null 2>&1; then
    printf 'Lab 5 ordinary egress unexpectedly reached example.com\n' >&2
    exit 1
else
    network_status=$?
fi

DENIAL_EVIDENCE="$EVIDENCE_DIR/network-denial.log"
denial_verified=false
for _ in $(seq 1 30); do
    if ! openshell logs "$SANDBOX" --source sandbox -n 300 >"$DENIAL_EVIDENCE"; then
        printf 'failed to retrieve Lab 5 denial audit events\n' >&2
        exit 1
    fi
    if grep -Eq \
        'NET:OPEN.*DENIED .*python3[^ ]*\([0-9]+\) -> example\.com:443' \
        "$DENIAL_EVIDENCE"; then
        denial_verified=true
        break
    fi
    sleep 1
done
[[ "$denial_verified" == true ]] || {
    printf 'example.com failed with status %s without a matching denial event\n' \
        "$network_status" >&2
    exit 1
}

PROCESS_EVIDENCE="$EVIDENCE_DIR/process-status.txt"
openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- /bin/sh -c \
    'grep -E "^(CapBnd|NoNewPrivs):" /proc/self/status' \
    >"$PROCESS_EVIDENCE"
grep -Eq '^CapBnd:[[:space:]]+0+$' "$PROCESS_EVIDENCE"
grep -Eq '^NoNewPrivs:[[:space:]]+1$' "$PROCESS_EVIDENCE"

openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- /usr/bin/test -x /usr/bin/unshare >/dev/null
if openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- /usr/bin/unshare -Urn true >/dev/null 2>&1; then
    printf 'Lab 5 process created a forbidden user/network namespace\n' >&2
    exit 1
fi

if ! openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- python3 -c \
    'import os, sys; names = ("OPENAI_API_KEY", "OPENAI_KEY", "AUTHORIZATION"); sys.exit(any(name in os.environ for name in names))' \
    >/dev/null 2>&1; then
    printf 'Lab 5 workload environment contains a forbidden credential name\n' >&2
    exit 1
fi

printf 'lab5 verification passed; sandbox and loopback forward remain running\n'
