#!/usr/bin/env bash
set -euo pipefail

gpu_names=$(nvidia-smi --query-gpu=name --format=csv,noheader) || {
    printf 'unable to query the GPU topology\n' >&2
    exit 1
}
gpu_count=$(printf '%s\n' "$gpu_names" | awk 'NF { count += 1 } END { print count + 0 }')
l4_count=$(printf '%s\n' "$gpu_names" | awk '$0 == "NVIDIA L4" { count += 1 } END { print count + 0 }')
l40s_count=$(printf '%s\n' "$gpu_names" | awk '$0 == "NVIDIA L40S" { count += 1 } END { print count + 0 }')

if [[ "$gpu_count" -eq 4 && "$l4_count" -eq 4 ]]; then
    printf 'g6-l4 16\n'
elif [[ "$gpu_count" -eq 4 && "$l40s_count" -eq 4 ]]; then
    printf 'g6e-l40s 256\n'
else
    printf 'unsupported GPU topology: expected four homogeneous NVIDIA L4 or NVIDIA L40S GPUs\n' >&2
    exit 1
fi
