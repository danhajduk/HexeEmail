#!/usr/bin/env bash
set -euo pipefail

exec uvicorn main:create_app --factory --app-dir src --host 0.0.0.0 --port 8080
