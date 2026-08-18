#!/usr/bin/env bash
set -euo pipefail

SANDBOX="openshell-lab1"

expect_denied() {
    local description=$1
    shift
    if "$@"; then
        printf 'expected denial succeeded unexpectedly: %s\n' "$description" >&2
        exit 1
    fi
    printf 'verified denial: %s\n' "$description"
}

openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/curl --silent --show-error --fail-with-body \
    https://api.github.com/repos/NVIDIA/OpenShell >/dev/null

expect_denied "curl to an unlisted host" \
    openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/curl --silent --show-error --fail-with-body https://example.com/

expect_denied "Python direct network access" \
    openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    python3 -c 'import socket; socket.create_connection(("api.github.com", 443), 10)'

expect_denied "GitHub POST through read-only REST policy" \
    openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/curl --silent --show-error --fail-with-body \
    --request POST https://api.github.com/rate_limit

openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /sandbox/lab1-workdir-write-allowed
openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /tmp/lab1-tmp-write-allowed

logs=$(openshell logs "$SANDBOX" --source sandbox -n 500)
grep -F "Landlock ruleset built" <<<"$logs" >/dev/null
openshell policy get "$SANDBOX" --full --output json | \
    grep -F '"include_workdir": true' >/dev/null
printf 'lab1 verification passed\n'
