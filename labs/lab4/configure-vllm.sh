#!/usr/bin/env bash
set -euo pipefail

readonly MODEL="Qwen/Qwen3.6-27B"
readonly IMAGE="docker.io/vllm/vllm-openai:v0.19.0"
readonly SERVICE="vllm.service"
readonly CACHE="$HOME/.cache/huggingface"

[[ $(nvidia-smi --query-gpu=name --format=csv,noheader | grep -c '^NVIDIA L40S$') -eq 4 ]] || {
    printf 'expected exactly four NVIDIA L40S GPUs\n' >&2
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
Exec=$MODEL --host 0.0.0.0 --port 8000 --dtype bfloat16 --tensor-parallel-size 4 --max-model-len 32768 --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder --language-model-only --disable-custom-all-reduce

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
    systemctl --user restart "$SERVICE"
fi
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user start "$SERVICE"
printf 'vLLM is starting; follow with: journalctl --user -u %s -f\n' "$SERVICE"
