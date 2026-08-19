#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=infra/aws/gpu-lib.sh
source "$SCRIPT_DIR/gpu-lib.sh"

validate_gpu_instance
state=$(gpu_field State.Name)
case "$state" in
    running | pending)
        gpu_aws ec2 stop-instances --instance-ids "$GPU_INSTANCE_ID" >/dev/null
        gpu_aws ec2 wait instance-stopped --instance-ids "$GPU_INSTANCE_ID"
        ;;
    stopped)
        ;;
    *)
        printf 'GPU instance cannot be stopped from state: %s\n' "$state" >&2
        exit 1
        ;;
esac
printf '%s\n' "$GPU_INSTANCE_ID"
