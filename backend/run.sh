#!/usr/bin/env bash
# Start the Meetingly API (works even when launched from AppImage shells)
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "Creating venv with uv…"
  command -v uv >/dev/null || { echo "Install uv: https://docs.astral.sh/uv/"; exit 1; }
  uv venv --python 3.12 .venv
  uv pip install -r requirements.txt
fi

# Avoid host AppImage LD_LIBRARY_PATH breaking the venv interpreter
exec env -u LD_LIBRARY_PATH -u APPDIR -u APPIMAGE -u PYTHONHOME \
  .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
