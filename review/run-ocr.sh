#!/usr/bin/env bash
set -euo pipefail

REVIEW_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$REVIEW_DIR/.." && pwd)
expected="f0c4554d5b6fad36a2878ff620e68d9e345c98af601eb1199542df9222ae1e7a"
actual=$(shasum -a 256 "$(command -v ocr)" | cut -d ' ' -f1)
[[ "$actual" == "$expected" ]] || {
    printf 'OpenCodeReview checksum mismatch\n' >&2
    exit 1
}
: "${OPENAI_API_KEY:?OpenCodeReview requires OPENAI_API_KEY in the environment}"

ocr scan \
    --repo "$ROOT" \
    --provider openai \
    --model gpt-5.5 \
    --format json \
    --audience agent \
    --max-tokens-budget 120000 \
    --exclude '.git/**,.venv/**,evidence/**,review/ocr-*.json' \
    --background 'Review security, correctness, OpenShell policy least privilege, secret handling, failure behavior, and documentation accuracy. Treat unverified deployment claims as findings.' \
    >"$REVIEW_DIR/ocr-cpu.json"
