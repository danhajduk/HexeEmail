# Phase 1 Runbook

## First Boot

1. Copy `.env.example` values into your environment.
2. Start the node with `scripts/dev.sh`.
3. Wait for the node to print the approval URL.
4. Open the approval URL in Core and approve the node.
5. Confirm `GET /onboarding/status` returns `approved` and `GET /status` shows `trust_state=trusted`.

## Approval Flow

- On first boot, the node creates an onboarding session and persists the returned session metadata.
- The node keeps polling the finalize endpoint until Core returns a terminal state.
- On approval, trust and MQTT credentials are stored locally with restrictive file permissions.

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
