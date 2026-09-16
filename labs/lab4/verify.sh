#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
SANDBOX="openshell-lab4"
IMAGE_STATE="$ROOT/state/lab4-image.env"
FORWARD_UNIT="openshell-lab4-forward.service"
EVIDENCE_DIR="$ROOT/evidence/cpu/lab4"

[[ -r "$IMAGE_STATE" ]] || {
    printf 'Lab 4 image state is missing or unreadable\n' >&2
    exit 1
}
IMAGE=$(awk -F= '$1 == "IMAGE" {print substr($0, index($0, "=") + 1)}' "$IMAGE_STATE")
[[ "$IMAGE" =~ ^localhost/openshell-lab-streamlit:[0-9a-f]{7,12}$ ]] || {
    printf 'Lab 4 image state is invalid\n' >&2
    exit 1
}

mkdir -p "$EVIDENCE_DIR"
umask 077

identity=$(podman image inspect "$IMAGE" --format '{{.Config.User}}')
[[ "$identity" == "1500:1500" ]] || {
    printf 'Lab 4 image identity is not 1500:1500\n' >&2
    exit 1
}
printf '%s\n' "$identity" >"$EVIDENCE_DIR/image-identity.txt"

systemctl --user is-active --quiet "$FORWARD_UNIT" || {
    printf 'Lab 4 loopback forward service is not active\n' >&2
    exit 1
}
FORWARD_UNIT_EVIDENCE="$EVIDENCE_DIR/forward-unit.txt"
systemctl --user show "$FORWARD_UNIT" --property=ExecStart --value \
    >"$FORWARD_UNIT_EVIDENCE"
if ! grep -Fq 'openshell forward service openshell-lab4' "$FORWARD_UNIT_EVIDENCE" \
    || ! grep -Fq -- '--target-port 8501' "$FORWARD_UNIT_EVIDENCE" \
    || ! grep -Fq -- '--local 127.0.0.1:18401' "$FORWARD_UNIT_EVIDENCE" \
    || grep -Eq -- '--local (0\.0\.0\.0|\[?::\]?):18401' "$FORWARD_UNIT_EVIDENCE"; then
    printf 'Lab 4 forward unit is missing the approved mapping or contains a public bind\n' >&2
    exit 1
fi

LISTENER_EVIDENCE="$EVIDENCE_DIR/listener.txt"
ss -H -ltn 'sport = :18401' >"$LISTENER_EVIDENCE"
python3 - "$LISTENER_EVIDENCE" <<'PY'
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    listeners = [line.split()[3] for line in stream if line.strip()]
if listeners != ["127.0.0.1:18401"]:
    raise SystemExit(f"unexpected Lab 4 listeners: {listeners!r}")
PY
curl --silent --show-error --fail --max-time 10 \
    http://127.0.0.1:18401/_stcore/health \
    >"$EVIDENCE_DIR/health.txt"
[[ "$(<"$EVIDENCE_DIR/health.txt")" == "ok" ]]

POLICY_EVIDENCE="$EVIDENCE_DIR/policy.json"
openshell policy get "$SANDBOX" --full --output json >"$POLICY_EVIDENCE"
PYTHONPATH="$ROOT/src" python3 -m openshell_lab.lab4_policy "$POLICY_EVIDENCE"

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

FILESYSTEM_DENIAL_EVIDENCE="$EVIDENCE_DIR/filesystem-denial.txt"
if ! openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- python3 -c \
    'import errno; path = "/opt/openshell-lab/lab4-write-denied"; code = "try:\n open(path, \"w\").close()\nexcept OSError as error:\n assert error.errno in (errno.EACCES, errno.EPERM)\n print(\"filesystem-write-denied\")\nelse:\n raise RuntimeError(\"application directory accepted a write\")"; exec(code)' \
    >"$FILESYSTEM_DENIAL_EVIDENCE"; then
    printf 'Lab 4 filesystem denial probe failed or accepted a write\n' >&2
    exit 1
fi
grep -Fxq 'filesystem-write-denied' "$FILESYSTEM_DENIAL_EVIDENCE"

network_status=0
if openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 20 \
    -- python3 -c \
    'import httpx; response = httpx.get("https://example.com", timeout=10); response.raise_for_status()' \
    >/dev/null 2>&1; then
    printf 'Lab 4 ordinary egress unexpectedly reached example.com\n' >&2
    exit 1
else
    network_status=$?
fi

DENIAL_EVIDENCE="$EVIDENCE_DIR/network-denial.log"
denial_verified=false
for _ in $(seq 1 30); do
    if ! openshell logs "$SANDBOX" --source sandbox -n 300 >"$DENIAL_EVIDENCE"; then
        printf 'failed to retrieve Lab 4 denial audit events\n' >&2
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
    'grep -E "^(Uid|Gid|CapBnd|NoNewPrivs):" /proc/self/status' \
    >"$PROCESS_EVIDENCE"
grep -Eq '^Uid:[[:space:]]+1500([[:space:]]+1500){3}$' "$PROCESS_EVIDENCE"
grep -Eq '^Gid:[[:space:]]+1500([[:space:]]+1500){3}$' "$PROCESS_EVIDENCE"
grep -Eq '^CapBnd:[[:space:]]+0+$' "$PROCESS_EVIDENCE"
grep -Eq '^NoNewPrivs:[[:space:]]+1$' "$PROCESS_EVIDENCE"

openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- /usr/bin/test -x /usr/bin/unshare >/dev/null
NAMESPACE_DENIAL_EVIDENCE="$EVIDENCE_DIR/namespace-denial.txt"
if ! openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- python3 -c \
    'import subprocess; result = subprocess.run(["/usr/bin/unshare", "-Urn", "true"], capture_output=True, text=True); assert result.returncode == 1 and "Operation not permitted" in result.stderr; print("namespace-denied")' \
    >"$NAMESPACE_DENIAL_EVIDENCE"; then
    printf 'Lab 4 namespace denial probe failed or created a namespace\n' >&2
    exit 1
fi
grep -Fxq 'namespace-denied' "$NAMESPACE_DENIAL_EVIDENCE"

if ! openshell sandbox exec \
    --name "$SANDBOX" \
    --no-tty \
    --timeout 15 \
    -- python3 -c \
    'import os, sys; names = ("OPENAI_API_KEY", "OPENAI_KEY", "AUTHORIZATION"); sys.exit(any(name in os.environ for name in names))' \
    >/dev/null 2>&1; then
    printf 'Lab 4 workload environment contains a forbidden credential name\n' >&2
    exit 1
fi

printf 'lab4 verification passed; sandbox and loopback forward remain running\n'
