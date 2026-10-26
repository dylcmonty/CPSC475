#!/usr/bin/env bash
# Launch the Almanac demo. Creates .venv and installs requirements the
# first time, then hands off to scripts/demo.py. See that file for the
# commands: setup, check, reset, and start (the default).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

if [ ! -x "$VENV/bin/python" ]; then
    echo "First run: creating $VENV and installing requirements..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet -r "$ROOT/requirements.txt"
fi

exec "$VENV/bin/python" "$ROOT/scripts/demo.py" "$@"
