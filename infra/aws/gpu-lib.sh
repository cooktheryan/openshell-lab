#!/usr/bin/env bash
set -euo pipefail

readonly GPU_REGION="us-east-2"
readonly GPU_INSTANCE_ID="i-000d2fc821040d9e3"
readonly GPU_INSTANCE_TYPE="g6e.12xlarge"
readonly GPU_AMI_ID="ami-0cbb38e3582830ad2"
readonly GPU_PROJECT_TAG="single-server-shell"
readonly GPU_NAME_TAG="openshell-qwen36-single-server"
readonly GPU_OWNER_TAG="rcook"

GPU_AWS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
GPU_REPOSITORY_ROOT=$(cd -- "$GPU_AWS_DIR/../.." && pwd)
GPU_STATE_FILE="$GPU_REPOSITORY_ROOT/state/gpu-connection.env"

gpu_aws() {
    aws --no-cli-pager --region "$GPU_REGION" "$@"
}
gpu_field() {
    local query=$1
    gpu_aws ec2 describe-instances --instance-ids "$GPU_INSTANCE_ID" \
        --query "Reservations[0].Instances[0].${query}" --output text
}

validate_gpu_instance() {
    local snapshot expected
    snapshot=$(gpu_aws ec2 describe-instances --instance-ids "$GPU_INSTANCE_ID" \
        --query "Reservations[0].Instances[0].[InstanceType,ImageId,Tags[?Key=='Project'].Value | [0],Tags[?Key=='Name'].Value | [0],Tags[?Key=='Owner'].Value | [0],KeyName,length(SecurityGroups),SecurityGroups[0].GroupName]" \
        --output text)
    expected="$GPU_INSTANCE_TYPE"$'\t'"$GPU_AMI_ID"$'\t'"$GPU_PROJECT_TAG"$'\t'"$GPU_NAME_TAG"$'\t'"$GPU_OWNER_TAG"$'\t'rcook$'\t'1$'\t'wide
    [[ "$snapshot" == "$expected" ]] || {
        printf 'GPU instance identity validation failed; refusing mutation\n' >&2
        exit 1
    }
}

write_gpu_state() (
    local public_ip private_ip temporary
    public_ip=$(gpu_field PublicIpAddress)
    private_ip=$(gpu_field PrivateIpAddress)
    [[ "$public_ip" =~ ^[0-9.]+$ && "$private_ip" =~ ^[0-9.]+$ ]] || {
        printf 'GPU instance has no usable network addresses\n' >&2
        exit 1
    }
    mkdir -p "$(dirname -- "$GPU_STATE_FILE")"
    umask 077
    temporary=$(mktemp "${GPU_STATE_FILE}.XXXXXX")
    {
        printf 'AWS_REGION=%q\n' "$GPU_REGION"
        printf 'INSTANCE_ID=%q\n' "$GPU_INSTANCE_ID"
        printf 'PUBLIC_IP=%q\n' "$public_ip"
        printf 'PRIVATE_IP=%q\n' "$private_ip"
        printf 'SSH_USER=ec2-user\n'
        printf 'SSH_KEY_PATH=%q\n' "$HOME/.ssh/id_rsa"
    } >"$temporary"
    chmod 0600 "$temporary"
    mv "$temporary" "$GPU_STATE_FILE"
)
