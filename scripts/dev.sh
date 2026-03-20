#!/usr/bin/env bash
set -euo pipefail

exec uvicorn email_node.main:create_app --factory --host 0.0.0.0 --port 8080
