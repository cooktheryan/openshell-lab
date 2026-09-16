#!/usr/bin/env bash
# shellcheck disable=SC1091,SC2016,SC2029
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=infra/aws/lib.sh
source "$ROOT/infra/aws/lib.sh"
# shellcheck source=scripts/credential-patterns.sh
source "$ROOT/scripts/credential-patterns.sh"

load_cpu_state
PUBLIC_IP=$(state_value PUBLIC_IP)
SSH_USER=$(state_value SSH_USER)
SSH_KEY_PATH=$(state_value SSH_KEY_PATH)
KNOWN_HOSTS="$ROOT/state/known_hosts"
EVIDENCE="$ROOT/evidence/cpu"
mkdir -p "$EVIDENCE"

umask 077
cpu_lock="$ROOT/evidence/.cpu-collect.lock"
cpu_lock_acquired=false
lab4_transfer=
lab4_stage=
lab4_previous="$EVIDENCE/.lab4-previous.$$"

cleanup_cpu_collection() {
    if [[ -n "$lab4_transfer" && -d "$lab4_transfer" ]]; then
        rm -rf -- "$lab4_transfer"
    fi
    if [[ -n "$lab4_stage" && -d "$lab4_stage" ]]; then
        rm -rf -- "$lab4_stage"
    fi
    if [[ -d "$lab4_previous" ]]; then
        if [[ ! -e "$EVIDENCE/lab4" ]]; then
            mv "$lab4_previous" "$EVIDENCE/lab4"
        else
            rm -rf -- "$lab4_previous"
        fi
    fi
    if [[ "$cpu_lock_acquired" == true ]]; then
        rmdir -- "$cpu_lock"
    fi
}
trap cleanup_cpu_collection EXIT

if ! mkdir -- "$cpu_lock"; then
    printf 'CPU evidence collection is already running\n' >&2
    exit 1
fi
cpu_lock_acquired=true

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
        -e "s/${OPENAI_SECRET_PATTERN}/[REDACTED]/g" \
        -e "s/${AWS_ACCESS_KEY_ID_PATTERN}/[REDACTED]/g" \
        -e "s/${AWS_LABELED_SECRET_PATTERN}/\\1[REDACTED]/g" \
        -e "s/${AUTHORIZATION_VALUE_PATTERN}/\\1[REDACTED]/Ig"
}

remote 'set -e; openshell --version; podman --version; python3 --version; httpd -v | head -1; getenforce; swapon --show --bytes' \
    | redact >"$EVIDENCE/versions-and-platform.txt"
remote 'set -e; systemctl --user is-active openshell-gateway podman.socket; sudo systemctl is-active httpd firewalld' \
    | redact >"$EVIDENCE/service-states.txt"
remote 'set -eu; repository="$HOME/git/openshell-lab"; cd "$repository"; openshell policy get openshell-lab1 --full --output json; openshell policy get openshell-lab2 --full --output json' \
    | redact >"$EVIDENCE/effective-policies.jsonl"
remote 'set -eu; repository="$HOME/git/openshell-lab"; cd "$repository"; openshell logs openshell-lab1 --source sandbox -n 500; openshell logs openshell-lab2 --source sandbox -n 500' \
    | redact >"$EVIDENCE/sandbox-logs.txt"

curl --silent --show-error --fail-with-body --max-time 30 \
    "http://$PUBLIC_IP/openshell-lab/nvidia-openshell-last-5-merges.md" \
    >"$EVIDENCE/nvidia-openshell-last-5-merges.md"
(
    cd "$EVIDENCE"
    shasum -a 256 nvidia-openshell-last-5-merges.md >report.sha256
)
remote 'set -eu; repository="$HOME/git/openshell-lab"; test -d "$repository/evidence/lab3"; tar -C "$repository/evidence" -cf - lab3' \
    | tar -C "$EVIDENCE" -xf -

lab4_transfer=$(mktemp -d "${TMPDIR:-/tmp}/openshell-lab4-evidence.XXXXXX")
lab4_stage=$(mktemp -d "$EVIDENCE/.lab4-stage.XXXXXX")
remote 'set -eu; repository="$HOME/git/openshell-lab"; test -d "$repository/evidence/cpu/lab4"; tar -C "$repository/evidence/cpu" -cf - lab4' \
    >"$lab4_transfer/lab4.tar"
tar -tf "$lab4_transfer/lab4.tar" >"$lab4_transfer/members.txt"
if awk '$0 !~ /^lab4(\/|$)/ {rejected=1} END {exit !rejected}' \
    "$lab4_transfer/members.txt"; then
    printf 'Lab 4 evidence archive contains an out-of-scope path\n' >&2
    exit 1
fi
if grep -Eq '(^|/)\.\.(/|$)|^/' "$lab4_transfer/members.txt"; then
    printf 'Lab 4 evidence archive contains an unsafe path\n' >&2
    exit 1
fi
if awk 'seen[$0]++ {duplicate=1} END {exit !duplicate}' \
    "$lab4_transfer/members.txt"; then
    printf 'Lab 4 evidence archive contains a duplicate archive member\n' >&2
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
if ! awk '
    NR == FNR { expected["lab4/" $0] = 1; next }
    $0 == "lab4" || $0 == "lab4/" {
        root_entries++
        if (root_entries > 1) invalid = 1
        next
    }
    !($0 in expected) { invalid = 1 }
    { count[$0]++ }
    END {
        for (name in expected) {
            if (count[name] != 1) invalid = 1
        }
        exit invalid
    }
' "$lab4_transfer/expected-lab4-files.txt" \
    "$lab4_transfer/members.txt"; then
    printf 'Lab 4 evidence archive member occurrences are not exact\n' >&2
    exit 1
fi
tar -tvf "$lab4_transfer/lab4.tar" >"$lab4_transfer/member-types.txt"
if awk '$1 !~ /^[-d]/ {found=1} END {exit !found}' \
    "$lab4_transfer/member-types.txt"; then
    printf 'Lab 4 evidence archive contains a link or special file\n' >&2
    exit 1
fi

mkdir -p "$lab4_transfer/extracted"
tar -C "$lab4_transfer/extracted" -xf "$lab4_transfer/lab4.tar"
if [[ ! -d "$lab4_transfer/extracted/lab4" ]]; then
    printf 'Lab 4 evidence archive does not contain the expected directory\n' >&2
    exit 1
fi
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
