#!/usr/bin/env bash
# shellcheck disable=SC1091,SC2016,SC2029
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=infra/aws/lib.sh
source "$ROOT/infra/aws/lib.sh"

_ssh() {
    ssh -n "${SSH_OPTIONS[@]}" "$SSH_USER@$PUBLIC_IP" "$@"
}

_ssh_with_stdin() {
    ssh "${SSH_OPTIONS[@]}" "$SSH_USER@$PUBLIC_IP" "$@"
}

"$ROOT/infra/aws/launch-cpu.sh" >/dev/null
load_cpu_state
PUBLIC_IP=$(state_value PUBLIC_IP)
SSH_USER=$(state_value SSH_USER)
SSH_KEY_PATH=$(state_value SSH_KEY_PATH)
[[ "$PUBLIC_IP" =~ ^[0-9.]+$ && -f "$SSH_KEY_PATH" ]] || {
    printf 'CPU connection state is incomplete\n' >&2
    exit 1
}

# wait_for_ssh: capture the first reachable host key, then require it thereafter.
KNOWN_HOSTS="$ROOT/state/known_hosts"
mkdir -p "$ROOT/state"
umask 077
known_hosts_tmp=$(mktemp "$ROOT/state/known_hosts.XXXXXX")
for _ in $(seq 1 60); do
    if ssh-keyscan -T 5 -H "$PUBLIC_IP" >"$known_hosts_tmp" 2>/dev/null \
        && [[ -s "$known_hosts_tmp" ]]; then
        mv "$known_hosts_tmp" "$KNOWN_HOSTS"
        break
    fi
    sleep 5
done
[[ -s "$KNOWN_HOSTS" ]] || {
    printf 'SSH host key did not become available\n' >&2
    exit 1
}
SSH_OPTIONS=(
    -i "$SSH_KEY_PATH"
    -o BatchMode=yes
    -o ConnectTimeout=10
    -o StrictHostKeyChecking=yes
    -o "UserKnownHostsFile=$KNOWN_HOSTS"
)
for _ in $(seq 1 60); do
    if _ssh true 2>/dev/null; then
        break
    fi
    sleep 5
done
_ssh true

export RSYNC_RSH="ssh -i $SSH_KEY_PATH -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS"
_ssh 'mkdir -p "$HOME/git/openshell-lab"'
rsync -a --delete \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude 'state/' \
    --exclude '*.key' \
    --exclude '*.pem' \
    --exclude '.venv/' \
    --exclude '*.egg-info/' \
    --exclude 'models/' \
    --exclude '*.safetensors' \
    --exclude 'evidence/raw/' \
    --exclude 'results/raw/' \
    "$ROOT/" "$SSH_USER@$PUBLIC_IP:git/openshell-lab/"

_ssh 'cd "$HOME/git/openshell-lab" && ./infra/remote/bootstrap-rhel10.sh'

# configure_openai: stream the value over SSH stdin; never place it in argv.
model_key=${OPENAI_API_KEY:-}
if [[ -z "$model_key" ]]; then
    if [[ ! -t 0 ]]; then
        printf 'credential input requires a TTY or a pre-set environment value\n' >&2
        exit 1
    fi
    read -r -s -p 'OpenAI API key: ' model_key
    printf '\n' >&2
fi
printf '%s\n' "$model_key" | _ssh_with_stdin \
    'IFS= read -r OPENAI_API_KEY; export OPENAI_API_KEY; cd "$HOME/git/openshell-lab"; ./labs/lab1/configure-openai.sh'
unset model_key OPENAI_API_KEY

_ssh 'cd "$HOME/git/openshell-lab" && ./infra/remote/run-cpu-labs.sh'
_ssh 'cd "$HOME/git/openshell-lab" && ./scripts/scan-secrets.sh'
"$ROOT/scripts/collect-evidence.sh"

printf 'CPU labs complete: http://%s/openshell-lab/nvidia-openshell-last-5-merges.md\n' "$PUBLIC_IP"
