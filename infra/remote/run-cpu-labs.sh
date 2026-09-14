#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)

cd "$ROOT"
./labs/lab1/run.sh
./labs/lab1/verify.sh

./labs/lab2/configure-host.sh
./labs/lab2/run.sh
./labs/lab2/verify.sh
openshell forward stop 18080 openshell-lab2 >/dev/null

./labs/lab3/build.sh
./labs/lab3/run.sh
./labs/lab3/verify.sh

./labs/lab5/build.sh
./labs/lab5/run.sh
./labs/lab5/verify.sh
