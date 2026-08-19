#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="us-east-1"
# shellcheck disable=SC2034 # Constants are consumed by scripts that source this library.
readonly CPU_AMI_ID="ami-00adafae70b8029d8" \
    CPU_INSTANCE_TYPE="t3.micro" \
    CPU_KEY_NAME="rcook" \
    CPU_SECURITY_GROUP_NAME="wide"
PROJECT_TAG="openshell-four-labs"
ROLE_TAG="cpu"

AWS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPOSITORY_ROOT=$(cd -- "$AWS_DIR/../.." && pwd)
STATE_FILE="$REPOSITORY_ROOT/state/cpu-connection.env"

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        printf 'required command is unavailable: %s\n' "$1" >&2
        exit 1
    }
}

aws_cli() {
    aws --no-cli-pager --region "$AWS_REGION" "$@"
}

load_cpu_state() {
    [[ -f "$STATE_FILE" ]] || {
        printf 'CPU state file does not exist: %s\n' "$STATE_FILE" >&2
        exit 1
    }
    INSTANCE_ID=$(awk -F= '$1 == "INSTANCE_ID" {print substr($0, index($0, "=") + 1)}' "$STATE_FILE")
    SUBNET_ID=$(state_value SUBNET_ID)
    SECURITY_GROUP_ID=$(state_value SECURITY_GROUP_ID)
    [[ "$INSTANCE_ID" =~ ^i-[0-9a-f]+$ ]] || {
        printf 'CPU state contains an invalid instance ID\n' >&2
        exit 1
    }
    [[ "$SUBNET_ID" =~ ^subnet-[0-9a-f]+$ ]] || {
        printf 'CPU state contains an invalid subnet ID\n' >&2
        exit 1
    }
    [[ "$SECURITY_GROUP_ID" =~ ^sg-[0-9a-f]+$ ]] || {
        printf 'CPU state contains an invalid security group ID\n' >&2
        exit 1
    }
}

validate_project_instance() {
    local instance_id=$1
    local project role
    project=$(aws_cli ec2 describe-tags \
        --filters "Name=resource-id,Values=$instance_id" "Name=key,Values=Project" \
        --query 'Tags[0].Value' --output text)
    role=$(aws_cli ec2 describe-tags \
        --filters "Name=resource-id,Values=$instance_id" "Name=key,Values=Role" \
        --query 'Tags[0].Value' --output text)
    [[ "$project" == "$PROJECT_TAG" && "$role" == "$ROLE_TAG" ]] || {
        printf 'instance %s is not the managed CPU lab host\n' "$instance_id" >&2
        exit 1
    }
}

instance_state() {
    aws_cli ec2 describe-instances --instance-ids "$1" \
        --query 'Reservations[0].Instances[0].State.Name' --output text
}

write_cpu_state() (
    local instance_id=$1 subnet_id=$2 security_group_id=$3
    local phase=${4:-complete} public_ip="" private_ip="" temporary
    if [[ "$phase" == complete ]]; then
        public_ip=$(aws_cli ec2 describe-instances --instance-ids "$instance_id" \
            --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
        private_ip=$(aws_cli ec2 describe-instances --instance-ids "$instance_id" \
            --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)
        [[ "$public_ip" =~ ^[0-9.]+$ && "$private_ip" =~ ^[0-9.]+$ ]] || {
            printf 'CPU instance has no usable network addresses\n' >&2
            exit 1
        }
    elif [[ "$phase" != provisional ]]; then
        printf 'unsupported CPU state phase: %s\n' "$phase" >&2
        exit 1
    fi
    mkdir -p "$(dirname -- "$STATE_FILE")"
    umask 077
    temporary=$(mktemp "${STATE_FILE}.XXXXXX")
    {
        printf 'AWS_REGION=%q\n' "$AWS_REGION"
        printf 'INSTANCE_ID=%q\n' "$instance_id"
        printf 'PUBLIC_IP=%q\n' "$public_ip"
        printf 'PRIVATE_IP=%q\n' "$private_ip"
        printf 'SUBNET_ID=%q\n' "$subnet_id"
        printf 'SECURITY_GROUP_ID=%q\n' "$security_group_id"
        printf 'SSH_USER=ec2-user\n'
        printf 'SSH_KEY_PATH=%q\n' "$HOME/.ssh/id_rsa"
    } >"$temporary"
    chmod 0600 "$temporary"
    mv "$temporary" "$STATE_FILE"
)

state_value() {
    local key=$1
    awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1)}' "$STATE_FILE"
}
