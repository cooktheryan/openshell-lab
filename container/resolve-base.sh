#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repository="quay.io/aipcc/agentic-ci/openshell"
api="https://quay.io/api/v1/repository/aipcc/agentic-ci/openshell/tag/?onlyActiveTags=true&limit=100"

for command_name in curl jq skopeo sort; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'required command is unavailable: %s\n' "$command_name" >&2
        exit 1
    }
done

tag=$(curl --silent --show-error --fail-with-body --max-time 30 "$api" |
    jq -r '.tags[].name' |
    grep -E '^0\.3\.[0-9]+$' |
    sort -V |
    tail -n 1)
[[ "$tag" =~ ^0\.3\.[0-9]+$ ]] || {
    printf 'no stable 0.3.x tag was found\n' >&2
    exit 1
}

metadata=$(skopeo inspect --override-arch amd64 "docker://$repository:$tag")
digest=$(jq -er '.Digest | select(test("^sha256:[0-9a-f]{64}$"))' <<<"$metadata")
created=$(jq -er '.Created' <<<"$metadata")
architecture=$(jq -er '.Architecture' <<<"$metadata")
[[ "$architecture" == "amd64" ]] || {
    printf 'resolved image architecture is not amd64\n' >&2
    exit 1
}

temporary=$(mktemp "$SCRIPT_DIR/base-image.lock.XXXXXX")
{
    printf 'name=%s\n' "$repository"
    printf 'tag=%s\n' "$tag"
    printf 'digest=%s\n' "$digest"
    printf 'created=%s\n' "$created"
    printf 'architecture=%s\n' "$architecture"
    printf 'resolved_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >"$temporary"
mv "$temporary" "$SCRIPT_DIR/base-image.lock"
printf '%s@%s\n' "$repository" "$digest"
