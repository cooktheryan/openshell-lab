#!/usr/bin/env bash
# shellcheck disable=SC1091,SC2016,SC2029
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=infra/aws/lib.sh
source "$ROOT/infra/aws/lib.sh"

load_cpu_state
PUBLIC_IP=$(state_value PUBLIC_IP)
SSH_USER=$(state_value SSH_USER)
SSH_KEY_PATH=$(state_value SSH_KEY_PATH)
KNOWN_HOSTS="$ROOT/state/known_hosts"
EVIDENCE="$ROOT/evidence/cpu"
mkdir -p "$EVIDENCE"

SSH_OPTIONS=(
    -i "$SSH_KEY_PATH"
    -o BatchMode=yes
    -o StrictHostKeyChecking=yes
    -o "UserKnownHostsFile=$KNOWN_HOSTS"
)

remote() {
    ssh -n "${SSH_OPTIONS[@]}" "$SSH_USER@$PUBLIC_IP" "$@"
}

redact() {
    sed -E \
        -e 's/sk-[A-Za-z0-9_-]{20,}/[REDACTED]/g' \
        -e 's/AKIA[0-9A-Z]{16}/[REDACTED]/g' \
        -e 's/(Authorization: *(Bearer|Basic) +)[^ ]+/\1[REDACTED]/Ig'
}

remote 'set -e; openshell --version; podman --version; python3 --version; httpd -v | head -1; getenforce; swapon --show --bytes' \
    | redact >"$EVIDENCE/versions-and-platform.txt"
remote 'set -e; systemctl --user is-active openshell-gateway podman.socket; sudo systemctl is-active httpd firewalld' \
    | redact >"$EVIDENCE/service-states.txt"
remote 'cd "$HOME/git/openshell-lab"; openshell policy get openshell-lab1 --full --output json; openshell policy get openshell-lab2 --full --output json' \
    | redact >"$EVIDENCE/effective-policies.jsonl"
remote 'cd "$HOME/git/openshell-lab"; openshell logs openshell-lab1 --source sandbox -n 500; openshell logs openshell-lab2 --source sandbox -n 500' \
    | redact >"$EVIDENCE/sandbox-logs.txt"

curl --silent --show-error --fail-with-body --max-time 30 \
    "http://$PUBLIC_IP/openshell-lab/nvidia-openshell-last-5-merges.md" \
    >"$EVIDENCE/nvidia-openshell-last-5-merges.md"
(
    cd "$EVIDENCE"
    shasum -a 256 nvidia-openshell-last-5-merges.md >report.sha256
)
remote 'cd "$HOME/git/openshell-lab"; tar -C evidence -cf - lab3' \
    | tar -C "$EVIDENCE" -xf -

printf 'instance_id=%s\npublic_ip=%s\nreport_sha256=%s\n' \
    "$INSTANCE_ID" "$PUBLIC_IP" \
    "$(cut -d ' ' -f1 "$EVIDENCE/report.sha256")" \
    >"$EVIDENCE/summary.txt"
