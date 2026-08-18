#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=infra/aws/lib.sh
source "$SCRIPT_DIR/lib.sh"

require_command aws
load_cpu_state
validate_project_instance "$INSTANCE_ID"
current_state=$(instance_state "$INSTANCE_ID")
if [[ "$current_state" == "stopping" ]]; then
    aws_cli ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
    current_state="stopped"
fi
if [[ "$current_state" == "stopped" ]]; then
    aws_cli ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
elif [[ "$current_state" != "running" && "$current_state" != "pending" ]]; then
    printf 'instance cannot be started from state %s\n' "$current_state" >&2
    exit 1
fi
aws_cli ec2 wait instance-running --instance-ids "$INSTANCE_ID"
aws_cli ec2 wait instance-status-ok --instance-ids "$INSTANCE_ID"
write_cpu_state "$INSTANCE_ID" "$(state_value SUBNET_ID)" "$(state_value SECURITY_GROUP_ID)"
printf '%s\n' "$INSTANCE_ID"
