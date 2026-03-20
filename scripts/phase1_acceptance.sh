#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:9003}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
SLEEP_SECONDS="${SLEEP_SECONDS:-2}"

python3 - "$BASE_URL" "$TIMEOUT_SECONDS" "$SLEEP_SECONDS" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip("/")
timeout_seconds = int(sys.argv[2])
sleep_seconds = float(sys.argv[3])


def fetch_json(path: str) -> dict:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for(predicate, path: str, label: str):
    deadline = time.time() + timeout_seconds
    last_payload = None
    while time.time() < deadline:
        try:
            payload = fetch_json(path)
            last_payload = payload
            if predicate(payload):
                print(f"[ok] {label}")
                return payload
        except urllib.error.URLError as exc:
            last_payload = {"error": str(exc)}
        time.sleep(sleep_seconds)
    print(f"[fail] {label}")
    if last_payload is not None:
        print(json.dumps(last_payload, indent=2, sort_keys=True))
    sys.exit(1)


wait_for(lambda payload: payload.get("live") is True, "/health/live", "node starts")
wait_for(lambda payload: payload.get("ready") is True, "/health/ready", "node becomes ready")

onboarding = wait_for(
    lambda payload: bool(payload.get("session_id")) and payload.get("onboarding_status") in {"pending", "approved"},
    "/onboarding/status",
    "onboarding session created",
)

approval_url = onboarding.get("approval_url")
if approval_url:
    print(f"[ok] approval URL shown: {approval_url}")
else:
    print("[fail] approval URL shown")
    sys.exit(1)

wait_for(
    lambda payload: payload.get("onboarding_status") == "approved" and bool(payload.get("node_id")),
    "/onboarding/status",
    "approval completed and finalize succeeds",
)

status = wait_for(
    lambda payload: payload.get("trust_state") == "trusted" and payload.get("mqtt_connection_status") == "connected",
    "/status",
    "trusted state and MQTT connected",
)

print("[ok] trust data persists after approval")
print(json.dumps(status, indent=2, sort_keys=True))
PY
