#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=infra/aws/lib.sh
source "$SCRIPT_DIR/lib.sh"

require_command aws
mkdir -p "$(dirname -- "$STATE_FILE")"
launch_lock="${STATE_FILE}.launch.lock"
if ! mkdir -- "$launch_lock"; then
    printf 'another CPU launch is already in progress: %s\n' "$launch_lock" >&2
    exit 1
fi
trap 'rmdir -- "$launch_lock"' EXIT

if [[ -f "$STATE_FILE" ]]; then
    load_cpu_state
    validate_project_instance "$INSTANCE_ID"
    current_state=$(instance_state "$INSTANCE_ID")
    if [[ "$current_state" != "terminated" && "$current_state" != "shutting-down" ]]; then
        printf '%s\n' "$INSTANCE_ID"
        exit 0
    fi
    printf 'managed instance in state %s cannot be reused; archive %s first\n' \
        "$current_state" "$STATE_FILE" >&2
    exit 1
fi

vpc_id=$(aws_cli ec2 describe-vpcs \
    --filters 'Name=is-default,Values=true' \
    --query 'Vpcs[0].VpcId' --output text)
[[ "$vpc_id" =~ ^vpc-[0-9a-f]+$ ]] || {
    printf 'default VPC resolution failed\n' >&2
    exit 1
}

security_group_id=$(aws_cli ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$vpc_id" \
        "Name=group-name,Values=$CPU_SECURITY_GROUP_NAME" \
    --query 'SecurityGroups[0].GroupId' --output text)
[[ "$security_group_id" =~ ^sg-[0-9a-f]+$ ]] || {
    printf 'security group resolution failed\n' >&2
    exit 1
}

subnet_id=$(aws_cli ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$vpc_id" 'Name=state,Values=available' \
        'Name=map-public-ip-on-launch,Values=true' \
    --query 'sort_by(Subnets,&AvailabilityZone)[0].SubnetId' --output text)
[[ "$subnet_id" =~ ^subnet-[0-9a-f]+$ ]] || {
    printf 'public default subnet resolution failed\n' >&2
    exit 1
}

image_description=$(aws_cli ec2 describe-images --image-ids "$CPU_AMI_ID" \
    --query 'Images[0].[ImageId,State,Architecture,RootDeviceType]' --output text)
[[ "$image_description" == "$CPU_AMI_ID"$'\t'available$'\t'x86_64$'\t'ebs ]] || {
    printf 'approved RHEL image validation failed: %s\n' "$image_description" >&2
    exit 1
}
aws_cli ec2 describe-key-pairs --key-names "$CPU_KEY_NAME" \
    --query 'KeyPairs[0].KeyName' --output text | grep -Fx "$CPU_KEY_NAME" >/dev/null

existing=$(aws_cli ec2 describe-instances \
    --filters "Name=tag:Project,Values=$PROJECT_TAG" "Name=tag:Role,Values=$ROLE_TAG" \
        'Name=instance-state-name,Values=pending,running,stopping,stopped' \
    --query 'Reservations[].Instances[].InstanceId' --output text)
[[ -z "$existing" ]] || {
    printf 'a managed CPU lab instance already exists: %s\n' "$existing" >&2
    exit 1
}

instance_id=$(aws_cli ec2 run-instances \
    --image-id "$CPU_AMI_ID" \
    --instance-type "$CPU_INSTANCE_TYPE" \
    --count 1 \
    --key-name "$CPU_KEY_NAME" \
    --subnet-id "$subnet_id" \
    --security-group-ids "$security_group_id" \
    --associate-public-ip-address \
    --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3","Encrypted":true,"DeleteOnTermination":true}}]' \
    --tag-specifications \
        "ResourceType=instance,Tags=[{Key=Name,Value=openshell-cpu-labs},{Key=Project,Value=$PROJECT_TAG},{Key=Role,Value=$ROLE_TAG}]" \
        "ResourceType=volume,Tags=[{Key=Project,Value=$PROJECT_TAG},{Key=Role,Value=$ROLE_TAG}]" \
    --query 'Instances[0].InstanceId' --output text)
[[ "$instance_id" =~ ^i-[0-9a-f]+$ ]] || {
    printf 'EC2 returned an invalid instance ID\n' >&2
    exit 1
}
printf 'launched %s; waiting for EC2 health checks\n' "$instance_id" >&2
write_cpu_state "$instance_id" "$subnet_id" "$security_group_id" provisional
aws_cli ec2 wait instance-running --instance-ids "$instance_id"
aws_cli ec2 wait instance-status-ok --instance-ids "$instance_id"
validate_project_instance "$instance_id"
write_cpu_state "$instance_id" "$subnet_id" "$security_group_id"
printf '%s\n' "$instance_id"
