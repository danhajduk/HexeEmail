#!/usr/bin/env bash
set -euo pipefail

PORT="${API_PORT:-9002}"
exec uvicorn main:create_app --factory --app-dir src --host 0.0.0.0 --port "${PORT}"
