#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/scripts/stack.env"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/runtime/logs"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Copy scripts/stack.env.example to scripts/stack.env and configure commands."
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$ENV_FILE"
}

require_cmds() {
  if [[ -z "${BACKEND_CMD:-}" ]]; then
    echo "BACKEND_CMD is empty in $ENV_FILE"
    exit 1
  fi
  if [[ -z "${FRONTEND_CMD:-}" ]]; then
    echo "FRONTEND_CMD is empty in $ENV_FILE"
    exit 1
  fi
}

prepare_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR"
}

is_running() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$pid_file")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

start_component() {
  local name="$1"
  local cmd="$2"
  local pid_file="$3"
  local log_file="$4"

  if is_running "$pid_file"; then
    echo "$name already running (pid $(cat "$pid_file"))"
    return
  fi

  echo "Starting $name..."
  (
    cd "${APP_DIR:-$ROOT_DIR}"
    nohup bash -lc "$cmd" >>"$log_file" 2>&1 &
    echo $! >"$pid_file"
  )
  echo "$name started (pid $(cat "$pid_file"))"
}

stop_component() {
  local name="$1"
  local pid_file="$2"

  if ! is_running "$pid_file"; then
    echo "$name not running"
    rm -f "$pid_file"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  echo "Stopping $name (pid $pid)..."
  kill "$pid" >/dev/null 2>&1 || true
  sleep 1
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$pid_file"
  echo "$name stopped"
}

status_component() {
  local name="$1"
  local pid_file="$2"
  if is_running "$pid_file"; then
    echo "$name: running (pid $(cat "$pid_file"))"
  else
    echo "$name: stopped"
  fi
}

port_listener_pid() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1
    return
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | awk -v port=":$port" '$4 ~ port { print $NF }' | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n 1
    return
  fi
  return 1
}

status_component_with_port() {
  local name="$1"
  local pid_file="$2"
  local port="$3"
  if is_running "$pid_file"; then
    echo "$name: running (pid $(cat "$pid_file"))"
    return
  fi

  local pid=""
  pid="$(port_listener_pid "$port" || true)"
  if [[ -n "$pid" ]]; then
    echo "$name: running (pid $pid, unmanaged)"
  else
    echo "$name: stopped"
  fi
}

main() {
  if [[ -z "$ACTION" ]]; then
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
  fi

  load_env
  require_cmds
  prepare_dirs

  case "$ACTION" in
    start)
      start_component "backend" "$BACKEND_CMD" "$BACKEND_PID_FILE" "$LOG_DIR/api.log"
      start_component "frontend" "$FRONTEND_CMD" "$FRONTEND_PID_FILE" "$LOG_DIR/ui.log"
      ;;
    stop)
      stop_component "frontend" "$FRONTEND_PID_FILE"
      stop_component "backend" "$BACKEND_PID_FILE"
      ;;
    restart)
      "$0" stop
      "$0" start
      ;;
    status)
      local api_port="${API_PORT:-9003}"
      local ui_port="${UI_PORT:-8083}"
      status_component_with_port "backend" "$BACKEND_PID_FILE" "$api_port"
      status_component_with_port "frontend" "$FRONTEND_PID_FILE" "$ui_port"
      if command -v curl >/dev/null 2>&1; then
        if curl -fsS "http://127.0.0.1:${api_port}/health/live" >/dev/null 2>&1; then
          echo "backend_http: healthy (http://127.0.0.1:${api_port}/health/live)"
        else
          echo "backend_http: unavailable (http://127.0.0.1:${api_port}/health/live)"
        fi
        if curl -fsS "http://127.0.0.1:${ui_port}" >/dev/null 2>&1; then
          echo "frontend_http: reachable (http://127.0.0.1:${ui_port})"
        else
          echo "frontend_http: unavailable (http://127.0.0.1:${ui_port})"
        fi
      fi
      ;;
    *)
      echo "Unknown action: $ACTION"
      exit 1
      ;;
  esac
}

main "$@"
