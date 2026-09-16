#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
short_sha=$(git -C "$ROOT" rev-parse --short=12 HEAD)
[[ "$short_sha" =~ ^[0-9a-f]{7,12}$ ]] || {
    printf 'could not derive a Git commit tag\n' >&2
    exit 1
}
image="localhost/openshell-lab-streamlit:$short_sha"

podman build --tag "$image" --file "$ROOT/labs/lab4/Containerfile" "$ROOT"
identity=$(podman image inspect "$image" --format '{{.Config.User}}')
[[ "$identity" == "1500:1500" ]] || {
    printf 'image identity is not the required numeric non-root user\n' >&2
    exit 1
}

mkdir -p "$ROOT/state"
umask 077
temporary=$(mktemp "$ROOT/state/lab4-image.env.XXXXXX")
trap 'rm -f -- "$temporary"' EXIT
printf 'IMAGE=%s\n' "$image" >"$temporary"
chmod 0600 "$temporary"
mv "$temporary" "$ROOT/state/lab4-image.env"
trap - EXIT
printf '%s\n' "$image"
