# Phase 1 Runbook

## First Boot

1. Copy `.env.example` values into your environment.
2. Start the node API with `scripts/dev.sh`.
3. Start the onboarding UI with `scripts/ui-dev.sh`.
4. Open `http://127.0.0.1:8083`.
5. Enter the Core base URL and node name.
6. Start onboarding from the UI.
7. Open the approval URL in Core and approve the node.
8. Confirm `GET /onboarding/status` returns `approved` and `GET /status` shows `trust_state=trusted`.
9. Use `Setup Provider` in the UI to continue into Gmail provider configuration when trust is active.

## Approval Flow

- On first boot, the node waits for operator-provided Core URL and node name unless they were already saved locally.
- After the operator saves configuration and starts onboarding, the node creates an onboarding session and persists the returned session metadata.
- The node keeps polling the finalize endpoint until Core returns a terminal state.
- On approval, trust and MQTT credentials are stored locally with restrictive file permissions.
- The React UI on port `8083` shows onboarding status, approval URL, trust state, MQTT connection state, and the provider setup entry point.

## Restart Behavior

- not onboarded: the node requests a fresh onboarding session
- pending session: the node resumes finalize polling
- trusted state: the node skips onboarding and connects operational MQTT
- corrupted local state: startup fails clearly and readiness remains false

## Acceptance Validation

Run `scripts/phase1_acceptance.sh` while the node is up and connected to a live Core deployment.

- the script verifies startup health
- it waits for onboarding session creation and approval URL surfacing
- after approval in Core, it verifies trusted state and MQTT connection
- restart verification is still a manual final step: restart the node and confirm `/status` returns `trust_state=trusted` without a new onboarding session

## Reset Procedure

- Stop the node.
- Run `scripts/reset_runtime.sh`.
- Start the node again to begin a fresh onboarding session.

## UI Ports

- local node API: `9003`
- onboarding UI: `8083`
