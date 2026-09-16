#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/credential-patterns.sh
source "$SCRIPT_DIR/credential-patterns.sh"

scan_root=${1:-.}
scan_root=$(cd "$scan_root" && pwd -P)

if ! git -C "$scan_root" rev-parse --git-dir >/dev/null 2>&1; then
    printf 'secret-scan: not a Git repository: %s\n' "$scan_root" >&2
    exit 2
fi

file_list=$(mktemp)
trap 'rm -f -- "$file_list"' EXIT
git -C "$scan_root" ls-files --cached --others --exclude-standard -z >"$file_list"

found=0
if command -v rg >/dev/null 2>&1; then
    search_file() {
        rg --quiet -- "$1" "$2"
    }
elif command -v grep >/dev/null 2>&1; then
    search_file() {
        grep -Eq -- "$1" "$2"
    }
else
    printf 'secret-scan: neither rg nor grep is available\n' >&2
    exit 2
fi

scan_rule() {
    rule_name=$1
    expression=$2
    while IFS= read -r -d '' relative_path; do
        absolute_path=$scan_root/$relative_path
        test -f "$absolute_path" || continue
        search_status=0
        search_file "$expression" "$absolute_path" || search_status=$?
        case "$search_status" in
            0)
                printf 'secret-scan: %s: %s\n' "$rule_name" "$relative_path"
                found=1
                ;;
            1)
                ;;
            *)
                printf 'secret-scan: search failed for %s (%s)\n' \
                    "$relative_path" "$rule_name" >&2
                exit 2
                ;;
        esac
    done <"$file_list"
}

scan_rule aws-access-key "$AWS_ACCESS_KEY_ID_PATTERN"
scan_rule aws-secret-value "$AWS_LABELED_SECRET_PATTERN"
scan_rule openai-secret "$OPENAI_SECRET_PATTERN"
scan_rule github-token "$GITHUB_SECRET_PATTERN"
scan_rule private-key-marker "$PRIVATE_KEY_MARKER_PATTERN"

if test "$found" -ne 0; then
    printf 'secret-scan: rejected credential-like content\n'
    exit 1
fi

printf 'secret-scan: clean\n'
