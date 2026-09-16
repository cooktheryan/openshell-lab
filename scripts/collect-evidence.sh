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

umask 077
lab4_transfer=$(mktemp -d "${TMPDIR:-/tmp}/openshell-lab4-evidence.XXXXXX")
lab4_stage=$(mktemp -d "$EVIDENCE/.lab4-stage.XXXXXX")
lab4_previous="$EVIDENCE/.lab4-previous.$$"
cleanup_lab4_transfer() {
    rm -rf -- "${lab4_transfer:?}"
    if [[ -n "${lab4_stage:-}" && -d "$lab4_stage" ]]; then
        rm -rf -- "$lab4_stage"
    fi
    if [[ -d "$lab4_previous" ]]; then
        if [[ ! -e "$EVIDENCE/lab4" ]]; then
            mv "$lab4_previous" "$EVIDENCE/lab4"
        else
            rm -rf -- "$lab4_previous"
        fi
    fi
}
trap cleanup_lab4_transfer EXIT
remote 'cd "$HOME/git/openshell-lab"; tar -C evidence/cpu -cf - lab4' \
    >"$lab4_transfer/lab4.tar"
tar -tf "$lab4_transfer/lab4.tar" >"$lab4_transfer/members.txt"
if grep -Ev '^lab4(/|$)' "$lab4_transfer/members.txt" | grep -q .; then
    printf 'Lab 4 evidence archive contains an out-of-scope path\n' >&2
    exit 1
fi
if grep -Eq '(^|/)\.\.(/|$)|^/' "$lab4_transfer/members.txt"; then
    printf 'Lab 4 evidence archive contains an unsafe path\n' >&2
    exit 1
fi
mkdir -p "$lab4_transfer/extracted"
tar -C "$lab4_transfer/extracted" -xf "$lab4_transfer/lab4.tar"
if find "$lab4_transfer/extracted/lab4" -type l -print -quit | grep -q .; then
    printf 'Lab 4 evidence archive contains a symbolic link\n' >&2
    exit 1
fi
printf '%s\n' \
    filesystem-denial.txt \
    forward-unit.txt \
    health.txt \
    image-identity.txt \
    listener.txt \
    namespace-denial.txt \
    network-denial.log \
    policy.json \
    probe.json \
    process-status.txt \
    sandbox-create.log \
    >"$lab4_transfer/expected-lab4-files.txt"
find "$lab4_transfer/extracted/lab4" -type f -print \
    | sed "s|^$lab4_transfer/extracted/lab4/||" \
    | LC_ALL=C sort >"$lab4_transfer/actual-lab4-files.txt"
if ! cmp -s \
    "$lab4_transfer/expected-lab4-files.txt" \
    "$lab4_transfer/actual-lab4-files.txt"; then
    printf 'Lab 4 evidence artifact set is incomplete or unexpected\n' >&2
    exit 1
fi
while IFS= read -r -d '' source; do
    relative=${source#"$lab4_transfer/extracted/lab4/"}
    destination="$lab4_stage/$relative"
    mkdir -p "$(dirname -- "$destination")"
    redact <"$source" >"$destination"
    chmod 0600 "$destination"
done < <(find "$lab4_transfer/extracted/lab4" -type f -print0)

if [[ -e "$EVIDENCE/lab4" ]]; then
    mv "$EVIDENCE/lab4" "$lab4_previous"
fi
if ! mv "$lab4_stage" "$EVIDENCE/lab4"; then
    if [[ -d "$lab4_previous" ]]; then
        mv "$lab4_previous" "$EVIDENCE/lab4"
    fi
    printf 'failed to replace Lab 4 evidence atomically\n' >&2
    exit 1
fi
lab4_stage=

printf 'instance_id=%s\npublic_ip=%s\nreport_sha256=%s\n' \
    "$INSTANCE_ID" "$PUBLIC_IP" \
    "$(cut -d ' ' -f1 "$EVIDENCE/report.sha256")" \
    >"$EVIDENCE/summary.txt"
