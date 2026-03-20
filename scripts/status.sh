#!/usr/bin/env bash
set -euo pipefail

PORT="${API_PORT:-9002}"
curl -fsS "http://127.0.0.1:${PORT}/status"
