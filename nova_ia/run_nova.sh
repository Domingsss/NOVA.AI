#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Ambiente virtual não encontrado. Execute:"
  echo "python3 -m venv --system-site-packages .venv"
  echo ".venv/bin/python -m pip install -r requirements-voice.txt"
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/src/main.py"
