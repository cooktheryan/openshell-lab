#!/usr/bin/env bash
# shellcheck disable=SC1091,SC2016,SC2029
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=infra/aws/gpu-lib.sh
source "$ROOT/infra/aws/gpu-lib.sh"
# shellcheck source=scripts/credential-patterns.sh
source "$ROOT/scripts/credential-patterns.sh"

if [[ ! -f "$GPU_STATE_FILE" ]]; then
    printf 'missing GPU connection state: %s\n' "$GPU_STATE_FILE" >&2
    exit 1
fi

gpu_state_value() {
    local key=$1
    awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1)}' \
        "$GPU_STATE_FILE"
}

PUBLIC_IP=$(gpu_state_value PUBLIC_IP)
SSH_USER=$(gpu_state_value SSH_USER)
SSH_KEY_PATH=$(gpu_state_value SSH_KEY_PATH)
KNOWN_HOSTS="$ROOT/state/gpu-known_hosts"
EVIDENCE_ROOT="$ROOT/evidence"
DESTINATION="$EVIDENCE_ROOT/gpu"

if [[ -z "$PUBLIC_IP" || -z "$SSH_USER" || -z "$SSH_KEY_PATH" ]]; then
    printf 'GPU connection state is incomplete\n' >&2
    exit 1
fi
if [[ ! -f "$KNOWN_HOSTS" ]]; then
    printf 'missing GPU known-hosts file: %s\n' "$KNOWN_HOSTS" >&2
    exit 1
fi

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

mkdir -p "$EVIDENCE_ROOT"
umask 077
gpu_lock="$EVIDENCE_ROOT/.gpu-collect.lock"
gpu_lock_acquired=false
gpu_transfer=
gpu_stage=
gpu_previous="$EVIDENCE_ROOT/.gpu-previous.$$"

cleanup_gpu_transfer() {
    if [[ -n "$gpu_transfer" && -d "$gpu_transfer" ]]; then
        rm -rf -- "$gpu_transfer"
    fi
    if [[ -n "${gpu_stage:-}" && -d "$gpu_stage" ]]; then
        rm -rf -- "$gpu_stage"
    fi
    if [[ -d "$gpu_previous" ]]; then
        if [[ ! -e "$DESTINATION" ]]; then
            mv "$gpu_previous" "$DESTINATION"
        else
            rm -rf -- "$gpu_previous"
        fi
    fi
    if [[ "$gpu_lock_acquired" == true ]]; then
        rmdir -- "$gpu_lock"
    fi
}
trap cleanup_gpu_transfer EXIT

if ! mkdir -- "$gpu_lock"; then
    printf 'GPU evidence collection is already running\n' >&2
    exit 1
fi
gpu_lock_acquired=true
gpu_transfer=$(mktemp -d "${TMPDIR:-/tmp}/openshell-gpu-evidence.XXXXXX")
gpu_stage=$(mktemp -d "$EVIDENCE_ROOT/.gpu-stage.XXXXXX")

remote 'set -eu; repository="$HOME/git/openshell-lab"; test -d "$repository/evidence/gpu"; tar -C "$repository/evidence" -cf - gpu' \
    >"$gpu_transfer/gpu.tar"
tar -tf "$gpu_transfer/gpu.tar" >"$gpu_transfer/members.txt"
if grep -Eq '(^|/)\.\.(/|$)|^/' "$gpu_transfer/members.txt"; then
    printf 'GPU evidence archive contains an unsafe path\n' >&2
    exit 1
fi
if awk '$0 !~ /^gpu(\/|$)/ {rejected=1} END {exit !rejected}' \
    "$gpu_transfer/members.txt"; then
    printf 'GPU evidence archive contains an out-of-scope path\n' >&2
    exit 1
fi
if awk 'seen[$0]++ {duplicate=1} END {exit !duplicate}' \
    "$gpu_transfer/members.txt"; then
    printf 'GPU evidence archive contains a duplicate archive member\n' >&2
    exit 1
fi
printf '%s\n' \
    agent-result.json \
    gpus.txt \
    policy.json \
    sandbox-create.log \
    >"$gpu_transfer/expected-gpu-files.txt"
if ! awk '
    NR == FNR { expected["gpu/" $0] = 1; next }
    $0 == "gpu" || $0 == "gpu/" {
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
' "$gpu_transfer/expected-gpu-files.txt" \
    "$gpu_transfer/members.txt"; then
    printf 'GPU evidence archive member occurrences are not exact\n' >&2
    exit 1
fi
tar -tvf "$gpu_transfer/gpu.tar" >"$gpu_transfer/member-types.txt"
if awk '$1 !~ /^[-d]/ {found=1} END {exit !found}' \
    "$gpu_transfer/member-types.txt"; then
    printf 'GPU evidence archive contains a link or special file\n' >&2
    exit 1
fi

mkdir -p "$gpu_transfer/extracted"
tar -C "$gpu_transfer/extracted" -xf "$gpu_transfer/gpu.tar"
if [[ ! -d "$gpu_transfer/extracted/gpu" ]]; then
    printf 'GPU evidence archive does not contain the expected directory\n' >&2
    exit 1
fi
if find "$gpu_transfer/extracted/gpu" -mindepth 1 ! -type f ! -type d \
    -print -quit | grep -q .; then
    printf 'GPU evidence archive contains a non-regular artifact\n' >&2
    exit 1
fi
if find "$gpu_transfer/extracted/gpu" -mindepth 1 -type d \
    -print -quit | grep -q .; then
    printf 'GPU evidence archive contains an unexpected directory\n' >&2
    exit 1
fi

find "$gpu_transfer/extracted/gpu" -type f -print \
    | sed "s|^$gpu_transfer/extracted/gpu/||" \
    | LC_ALL=C sort >"$gpu_transfer/actual-gpu-files.txt"
if ! cmp -s \
    "$gpu_transfer/expected-gpu-files.txt" \
    "$gpu_transfer/actual-gpu-files.txt"; then
    printf 'GPU evidence artifact set is incomplete or unexpected\n' >&2
    exit 1
fi

while IFS= read -r relative; do
    source="$gpu_transfer/extracted/gpu/$relative"
    destination="$gpu_stage/$relative"
    redact <"$source" >"$destination"
    chmod 0600 "$destination"
done <"$gpu_transfer/expected-gpu-files.txt"

if [[ -e "$gpu_previous" ]]; then
    printf 'GPU evidence recovery path already exists\n' >&2
    exit 1
fi
if [[ -e "$DESTINATION" ]]; then
    mv "$DESTINATION" "$gpu_previous"
fi
if ! mv "$gpu_stage" "$DESTINATION"; then
    if [[ -d "$gpu_previous" ]]; then
        mv "$gpu_previous" "$DESTINATION"
    fi
    printf 'failed to replace GPU evidence atomically\n' >&2
    exit 1
fi
gpu_stage=
