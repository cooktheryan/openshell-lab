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
lab5_transfer=$(mktemp -d "${TMPDIR:-/tmp}/openshell-lab5-evidence.XXXXXX")
lab5_stage=$(mktemp -d "$EVIDENCE/.lab5-stage.XXXXXX")
lab5_previous="$EVIDENCE/.lab5-previous.$$"
cleanup_lab5_transfer() {
    rm -rf -- "${lab5_transfer:?}"
    if [[ -n "${lab5_stage:-}" && -d "$lab5_stage" ]]; then
        rm -rf -- "$lab5_stage"
    fi
    if [[ -d "$lab5_previous" ]]; then
        if [[ ! -e "$EVIDENCE/lab5" ]]; then
            mv "$lab5_previous" "$EVIDENCE/lab5"
        else
            rm -rf -- "$lab5_previous"
        fi
    fi
}
trap cleanup_lab5_transfer EXIT
remote 'cd "$HOME/git/openshell-lab"; tar -C evidence/cpu -cf - lab5' \
    >"$lab5_transfer/lab5.tar"
tar -tf "$lab5_transfer/lab5.tar" >"$lab5_transfer/members.txt"
if grep -Ev '^lab5(/|$)' "$lab5_transfer/members.txt" | grep -q .; then
    printf 'Lab 5 evidence archive contains an out-of-scope path\n' >&2
    exit 1
fi
if grep -Eq '(^|/)\.\.(/|$)|^/' "$lab5_transfer/members.txt"; then
    printf 'Lab 5 evidence archive contains an unsafe path\n' >&2
    exit 1
fi
mkdir -p "$lab5_transfer/extracted"
tar -C "$lab5_transfer/extracted" -xf "$lab5_transfer/lab5.tar"
if find "$lab5_transfer/extracted/lab5" -type l -print -quit | grep -q .; then
    printf 'Lab 5 evidence archive contains a symbolic link\n' >&2
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
    >"$lab5_transfer/expected-lab5-files.txt"
find "$lab5_transfer/extracted/lab5" -type f -print \
    | sed "s|^$lab5_transfer/extracted/lab5/||" \
    | LC_ALL=C sort >"$lab5_transfer/actual-lab5-files.txt"
if ! cmp -s \
    "$lab5_transfer/expected-lab5-files.txt" \
    "$lab5_transfer/actual-lab5-files.txt"; then
    printf 'Lab 5 evidence artifact set is incomplete or unexpected\n' >&2
    exit 1
fi
while IFS= read -r -d '' source; do
    relative=${source#"$lab5_transfer/extracted/lab5/"}
    destination="$lab5_stage/$relative"
    mkdir -p "$(dirname -- "$destination")"
    redact <"$source" >"$destination"
    chmod 0600 "$destination"
done < <(find "$lab5_transfer/extracted/lab5" -type f -print0)

if [[ -e "$EVIDENCE/lab5" ]]; then
    mv "$EVIDENCE/lab5" "$lab5_previous"
fi
if ! mv "$lab5_stage" "$EVIDENCE/lab5"; then
    if [[ -d "$lab5_previous" ]]; then
        mv "$lab5_previous" "$EVIDENCE/lab5"
    fi
    printf 'failed to replace Lab 5 evidence atomically\n' >&2
    exit 1
fi
lab5_stage=

printf 'instance_id=%s\npublic_ip=%s\nreport_sha256=%s\n' \
    "$INSTANCE_ID" "$PUBLIC_IP" \
    "$(cut -d ' ' -f1 "$EVIDENCE/report.sha256")" \
    >"$EVIDENCE/summary.txt"
