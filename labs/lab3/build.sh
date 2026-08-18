#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)
short_sha=$(git -C "$ROOT" rev-parse --short=12 HEAD)
[[ "$short_sha" =~ ^[0-9a-f]{7,12}$ ]] || {
    printf 'could not derive a Git commit tag\n' >&2
    exit 1
}
image="localhost/openshell-lab-agent:$short_sha"

podman build --tag "$image" --file "$ROOT/container/Containerfile" "$ROOT"
identity=$(podman image inspect "$image" --format '{{.Config.User}}')
[[ "$identity" == "1500:1500" ]] || {
    printf 'image identity is not the required numeric non-root user\n' >&2
    exit 1
}

mkdir -p "$ROOT/state"
umask 077
temporary=$(mktemp "$ROOT/state/lab3-image.env.XXXXXX")
printf 'IMAGE=%s\n' "$image" >"$temporary"
chmod 0600 "$temporary"
mv "$temporary" "$ROOT/state/lab3-image.env"
printf '%s\n' "$image"
