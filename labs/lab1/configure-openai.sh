#!/usr/bin/env bash
set -euo pipefail

: "${OPENAI_API_KEY:?export OPENAI_API_KEY before running this command}"
provider_name="openai-gpt55"

if openshell provider get "$provider_name" >/dev/null 2>&1; then
    openshell provider update "$provider_name" --credential OPENAI_API_KEY >/dev/null
else
    openshell provider create \
        --name "$provider_name" \
        --type openai \
        --credential OPENAI_API_KEY >/dev/null
fi

openshell inference set \
    --provider "$provider_name" \
    --model gpt-5.5 \
    --timeout 180 >/dev/null
unset OPENAI_API_KEY
openshell inference get
