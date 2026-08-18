#!/usr/bin/env bash
set -euo pipefail

SANDBOX="openshell-lab2"
REPORT="nvidia-openshell-last-5-merges.md"

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
    /usr/bin/touch /var/www/html/lab2-write-allowed
expect_denied "workspace write outside webroot" \
    openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /sandbox/lab2-write-denied
openshell sandbox exec --name "$SANDBOX" --no-tty -- \
    /usr/bin/touch /tmp/lab2-runtime-write-allowed

test -s "/var/www/html/openshell-lab/$REPORT"
curl --silent --show-error --fail-with-body \
    "http://127.0.0.1/openshell-lab/$REPORT" | grep -F \
    '# NVIDIA/OpenShell: Last 5 Merged Pull Requests' >/dev/null
openshell policy get "$SANDBOX" --full --output json >/dev/null
printf 'lab2 verification passed\n'
