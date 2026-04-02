#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${API_PORT:-9003}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  exec "${ROOT_DIR}/.venv/bin/python" -m uvicorn main:create_app --factory --app-dir src --host 0.0.0.0 --port "${PORT}"
fi

exec python3 -m uvicorn main:create_app --factory --app-dir src --host 0.0.0.0 --port "${PORT}"
