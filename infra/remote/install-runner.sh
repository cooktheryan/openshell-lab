#!/usr/bin/env bash
# shellcheck disable=SC2016 # The generated runner must retain these variables.
set -euo pipefail

destination="$HOME/run-openshell-agent.sh"
temporary=$(mktemp "$HOME/run-openshell-agent.sh.XXXXXX")
for lab_name in lab1 lab2 lab3 lab4; do
    runner="$HOME/git/openshell-lab/labs/$lab_name/run.sh"
    [[ -x "$runner" ]] || {
        printf 'required lab runner is unavailable: %s\n' "$runner" >&2
        rm -f -- "$temporary"
        exit 1
    }
done
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'lab=${1:-}' \
    'if [[ -z "$lab" ]]; then' \
    '    if systemctl --user is-active --quiet vllm.service 2>/dev/null; then' \
    '        lab=lab4' \
    '    else' \
    '        lab=lab3' \
    '    fi' \
    'fi' \
    'case "$lab" in lab1|lab2|lab3|lab4) ;; *) echo "usage: $0 [lab1|lab2|lab3|lab4]" >&2; exit 2;; esac' \
    'cd "$HOME/git/openshell-lab"' \
    'runner="./labs/$lab/run.sh"' \
    '[[ -x "$runner" ]] || { echo "lab runner is unavailable: $runner" >&2; exit 1; }' \
    'exec "$runner"' >"$temporary"
chmod 0700 "$temporary"
mv "$temporary" "$destination"
printf '%s\n' "$destination"
