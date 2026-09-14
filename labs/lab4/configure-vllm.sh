#!/usr/bin/env bash
set -euo pipefail

readonly MODEL="Qwen/Qwen3.6-27B"
readonly IMAGE="docker.io/vllm/vllm-openai:v0.19.0"
readonly SERVICE="vllm.service"
readonly CACHE="$HOME/.cache/huggingface"
LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

gpu_profile_settings=$("$LAB_DIR/detect-gpu-profile.sh")
read -r GPU_PROFILE MAX_NUM_SEQS <<<"$gpu_profile_settings"
readonly gpu_profile_settings GPU_PROFILE MAX_NUM_SEQS
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
cdi_gpu_count=$(nvidia-ctk cdi list | grep -Ec '^nvidia\.com/gpu=[0-9]+$' || true)
[[ "$cdi_gpu_count" -eq 4 ]] || {
    printf 'expected CDI to expose exactly four numbered NVIDIA GPUs\n' >&2
    exit 1
}
podman info --format '{{.Host.Security.Rootless}}' | grep -Fx true >/dev/null
podman pull "$IMAGE"
install -d -m 0755 "$CACHE" "$HOME/.cache/vllm" \
    "$HOME/.config/containers/systemd"

unit="$HOME/.config/containers/systemd/vllm.container"
temporary=$(mktemp "$HOME/.config/containers/systemd/vllm.container.XXXXXX")
cat >"$temporary" <<EOF
[Unit]
Description=vLLM Qwen3.6-27B BF16 OpenAI-compatible service
After=network-online.target
Wants=network-online.target

[Container]
Image=$IMAGE
ContainerName=vllm-qwen36
Network=host
Volume=%h/.cache/huggingface:/root/.cache/huggingface:Z
Volume=%h/.cache/vllm:/root/.cache/vllm:Z
PodmanArgs=--security-opt=label=disable --device=nvidia.com/gpu=all --ipc=host
Exec=$MODEL --host 0.0.0.0 --port 8000 --dtype bfloat16 --tensor-parallel-size 4 --max-model-len 32768 --max-num-seqs $MAX_NUM_SEQS --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder --language-model-only --disable-custom-all-reduce

[Service]
Restart=on-failure
RestartSec=10
TimeoutStartSec=1800
TimeoutStopSec=120

[Install]
WantedBy=default.target
EOF
chmod 0644 "$temporary"
if [[ -f "$unit" ]] && cmp -s "$temporary" "$unit"; then
    rm -f "$temporary"
else
    mv "$temporary" "$unit"
    systemctl --user daemon-reload
fi
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user restart "$SERVICE"
printf 'vLLM is starting with profile %s; follow with: journalctl --user -u %s -f\n' \
    "$GPU_PROFILE" "$SERVICE"
