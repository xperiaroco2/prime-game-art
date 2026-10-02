#!/usr/bin/env bash
# prime-game-art task runner for bash (Git Bash on Windows): tools/run.sh <command> [args]
# Finds Python as PYTHON_BIN, else python3, else the py launcher, else python.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${PYTHON_BIN:-}" ]; then
  exec "$PYTHON_BIN" "$here/run.py" "$@"
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  exec python3 "$here/run.py" "$@"
elif command -v py >/dev/null 2>&1; then
  exec py -3 "$here/run.py" "$@"
else
  exec python "$here/run.py" "$@"
fi
