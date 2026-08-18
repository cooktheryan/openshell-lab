#!/usr/bin/env bash
set -euo pipefail

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
scan_rule() {
    rule_name=$1
    expression=$2
    while IFS= read -r -d '' relative_path; do
        absolute_path=$scan_root/$relative_path
        if test -f "$absolute_path" && rg --quiet --pcre2 -- "$expression" "$absolute_path"; then
            printf 'secret-scan: %s: %s\n' "$rule_name" "$relative_path"
            found=1
        fi
    done <"$file_list"
}

scan_rule aws-access-key 'AKIA[0-9A-Z]{16}'
scan_rule openai-secret 'sk-[A-Za-z0-9_-]{20,}'
scan_rule private-key-marker '-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'

if test "$found" -ne 0; then
    printf 'secret-scan: rejected credential-like content\n'
    exit 1
fi

printf 'secret-scan: clean\n'
