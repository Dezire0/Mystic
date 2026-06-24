#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${1:-base}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv-training}"
EXPAT_LIB="${EXPAT_LIB:-/opt/homebrew/opt/expat/lib}"

cd "$ROOT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

if [[ -d "$EXPAT_LIB" ]]; then
  export DYLD_LIBRARY_PATH="$EXPAT_LIB${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi

rm -rf "$VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip

case "$BACKEND" in
  base)
    python -m pip install -r requirements-training.txt
    ;;
  unsloth)
    python -m pip install -r requirements-unsloth.txt
    ;;
  axolotl)
    python -m pip install -r requirements-axolotl.txt
    ;;
  *)
    echo "Unknown backend: $BACKEND" >&2
    exit 1
    ;;
esac

python scripts/check_training_env.py
