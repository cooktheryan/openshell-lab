#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=infra/aws/gpu-lib.sh
source "$SCRIPT_DIR/gpu-lib.sh"

command -v aws >/dev/null 2>&1 || {
    printf 'AWS CLI is required\n' >&2
    exit 1
}
validate_gpu_instance
state=$(gpu_field State.Name)
case "$state" in
    stopped)
        gpu_aws ec2 start-instances --instance-ids "$GPU_INSTANCE_ID" >/dev/null
        ;;
    pending | running)
        ;;
    *)
        printf 'GPU instance cannot be started from state: %s\n' "$state" >&2
        exit 1
        ;;
esac
gpu_aws ec2 wait instance-running --instance-ids "$GPU_INSTANCE_ID"
gpu_aws ec2 wait instance-status-ok --instance-ids "$GPU_INSTANCE_ID"
validate_gpu_instance
write_gpu_state
printf '%s\n' "$GPU_INSTANCE_ID"
