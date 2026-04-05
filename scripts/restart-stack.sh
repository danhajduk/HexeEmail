#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_SCRIPT="$ROOT_DIR/scripts/bootstrap.sh"
STACK_CONTROL_SCRIPT="$ROOT_DIR/scripts/stack-control.sh"
BACKEND_SERVICE="hexe-email-node-backend.service"
FRONTEND_SERVICE="hexe-email-node-frontend.service"

have_user_units() {
  systemctl --user list-unit-files | grep -Eq "^${BACKEND_SERVICE}|^${FRONTEND_SERVICE}"
}

print_failure_logs() {
  local svc="$1"
  echo "---- ${svc} recent logs ----"
  journalctl --user -u "$svc" -n 40 --no-pager || true
}

if have_user_units; then
  echo "Reloading user systemd and restarting services..."
  systemctl --user daemon-reload
  systemctl --user restart "$BACKEND_SERVICE" "$FRONTEND_SERVICE"

  backend_active="unknown"
  frontend_active="unknown"
  backend_active="$(systemctl --user is-active "$BACKEND_SERVICE" || true)"
  frontend_active="$(systemctl --user is-active "$FRONTEND_SERVICE" || true)"

  systemctl --user status "$BACKEND_SERVICE" --no-pager -n 8 || true
  systemctl --user status "$FRONTEND_SERVICE" --no-pager -n 8 || true

  if [[ "$backend_active" != "active" ]]; then
    print_failure_logs "$BACKEND_SERVICE"
  fi
  if [[ "$frontend_active" != "active" ]]; then
    print_failure_logs "$FRONTEND_SERVICE"
  fi
else
  if [[ -x "$BOOTSTRAP_SCRIPT" ]]; then
    echo "User systemd units not installed. Installing from templates..."
    "$BOOTSTRAP_SCRIPT"
    systemctl --user daemon-reload
    systemctl --user restart "$BACKEND_SERVICE" "$FRONTEND_SERVICE"
    systemctl --user status "$BACKEND_SERVICE" --no-pager -n 8 || true
    systemctl --user status "$FRONTEND_SERVICE" --no-pager -n 8 || true
  elif [[ -x "$STACK_CONTROL_SCRIPT" ]]; then
    echo "systemd flow unavailable. Falling back to local stack-control script."
    "$STACK_CONTROL_SCRIPT" restart
    "$STACK_CONTROL_SCRIPT" status
  else
    echo "No restart method available."
    exit 1
  fi
fi
