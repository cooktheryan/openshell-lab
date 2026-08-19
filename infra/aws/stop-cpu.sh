#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=infra/aws/lib.sh
source "$SCRIPT_DIR/lib.sh"

require_command aws
load_cpu_state
validate_project_instance "$INSTANCE_ID"
current_state=$(instance_state "$INSTANCE_ID")
if [[ "$current_state" == "pending" ]]; then
    aws_cli ec2 wait instance-running --instance-ids "$INSTANCE_ID"
    current_state=$(instance_state "$INSTANCE_ID")
fi
if [[ "$current_state" == "running" ]]; then
    aws_cli ec2 stop-instances --instance-ids "$INSTANCE_ID" >/dev/null
    aws_cli ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
elif [[ "$current_state" == "stopping" ]]; then
    aws_cli ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
elif [[ "$current_state" != "stopped" ]]; then
    printf 'instance cannot be stopped from state %s\n' "$current_state" >&2
    exit 1
fi
printf '%s\n' "$INSTANCE_ID"
