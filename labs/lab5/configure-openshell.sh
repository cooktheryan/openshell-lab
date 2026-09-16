#!/usr/bin/env bash
set -euo pipefail

readonly PROVIDER="qwen36-local"
readonly MODEL="Qwen/Qwen3.6-27B"
readonly BASE_URL="http://host.openshell.internal:8000/v1"

curl --silent --show-error --fail http://127.0.0.1:8000/v1/models \
    | grep -F "$MODEL" >/dev/null

export OPENAI_API_KEY="not-used-local-vllm"
if openshell provider get "$PROVIDER" >/dev/null 2>&1; then
    openshell provider update "$PROVIDER" \
        --credential OPENAI_API_KEY \
        --config "OPENAI_BASE_URL=$BASE_URL" >/dev/null
else
    openshell provider create --name "$PROVIDER" --type openai \
        --credential OPENAI_API_KEY \
        --config "OPENAI_BASE_URL=$BASE_URL" >/dev/null
fi
unset OPENAI_API_KEY
openshell inference set --provider "$PROVIDER" --model "$MODEL" \
    --timeout 900 --no-verify >/dev/null
openshell inference get
