#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=infra/aws/lib.sh
source "$SCRIPT_DIR/lib.sh"

require_command aws
load_cpu_state
validate_project_instance "$INSTANCE_ID"
aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name,Type:InstanceType,PublicIp:PublicIpAddress,PrivateIp:PrivateIpAddress,ImageId:ImageId,LaunchTime:LaunchTime}' \
    --output json
