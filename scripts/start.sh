#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="python3"

api_pid=""
ui_pid=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  if [[ -n "${api_pid}" ]] && kill -0 "${api_pid}" 2>/dev/null; then
    kill "${api_pid}" 2>/dev/null || true
  fi

  if [[ -n "${ui_pid}" ]] && kill -0 "${ui_pid}" 2>/dev/null; then
    kill "${ui_pid}" 2>/dev/null || true
  fi

  wait "${api_pid}" 2>/dev/null || true
  wait "${ui_pid}" 2>/dev/null || true

  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

cd "${ROOT_DIR}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi

echo "[setup] Installing Python requirements"
"${PYTHON_BIN}" -m pip install -r "${ROOT_DIR}/requirements-dev.txt"

stdbuf -oL -eL ./scripts/dev.sh 2>&1 | sed 's/^/[api] /' &
api_pid=$!

stdbuf -oL -eL ./scripts/ui-dev.sh 2>&1 | sed 's/^/[ui]  /' &
ui_pid=$!

wait -n "${api_pid}" "${ui_pid}"
