#!/usr/bin/env bash
set -euo pipefail

cd frontend
API_PROXY_TARGET="${API_PROXY_TARGET:-http://127.0.0.1:9002}" exec npm run dev
