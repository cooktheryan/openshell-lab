#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
uv run python -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=src uv run behave features
uv run python /Users/rcook/.codex/skills/ears-gherkin-dev/scripts/audit.py \
    --specs-only features/
bash -n container/*.sh infra/aws/*.sh infra/remote/*.sh labs/*/*.sh scripts/*.sh review/*.sh
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck container/*.sh infra/aws/*.sh infra/remote/*.sh labs/*/*.sh scripts/*.sh review/*.sh
fi
uv run python -c 'from pathlib import Path; import yaml; [yaml.safe_load(p.read_text()) for p in Path("policies").glob("*.yaml")]'
jq -e '.type == "excalidraw"' diagrams/openshell-ai-application-workflow.excalidraw >/dev/null
./scripts/scan-secrets.sh .
git diff --check
printf 'local verification passed\n'
