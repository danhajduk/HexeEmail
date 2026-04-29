# Scheduler And Background Tasks

This document describes the recurring and long-lived background work that the email node owns today.

The canonical owner is [scheduler.py](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py). `NodeService` remains the public service surface, but all recurring loop state, schedule templates, due-window evaluation, and operator-facing scheduler snapshots delegate into `BackgroundTaskManager`.

Current scheduler task definitions are now centralized in the explicit registry:

- [BackgroundTaskManager.task_registry()](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py)

The registry is now the source of truth for stable task identity, task kind, owner, schedule name, and enabled-state intent for all currently modeled recurring work.

The scheduled-task snapshot is now built from that registry metadata as well, so task identity and operator-visible schedule metadata no longer need to be repeated separately in the snapshot builder.

## Owners

- `BackgroundTaskManager`: owns recurring loops, persisted scheduler state, schedule templates, due-slot logic, and operator-visible scheduler snapshots.
- `ProviderManager`: owns Gmail fetch execution and the last-hour Gmail processing pipeline.
- `GovernanceManager`: owns post-trust readiness refresh after provider state changes.
- `NotificationManager`: owns scheduler health notifications for Gmail fetch warning, error, and recovery transitions.

## Startup And Shutdown Gating

- Baseline runtime tasks (`heartbeat`, `telemetry`, `operational_mqtt_health`) start during scheduler startup.
- Provider-affecting recurring work does not start just because the process booted.
- Gmail status polling, Gmail fetch windows, and hourly batch classification now wait for:
  - `trust_state == trusted`
  - `operational_readiness == true`
- `GovernanceManager.update_operational_readiness()` now re-syncs scheduler gating so provider loops start only after readiness becomes true and are pushed back to idle when readiness drops.
- Scheduler shutdown now records explicit `stopped` task state for the long-lived loop-backed tasks instead of simply disappearing from memory.

## Recurring Tasks

### Baseline Runtime Tasks

- `heartbeat`
  - owner: `MQTTManager` heartbeat loop with state recorded by `BackgroundTaskManager`
  - schedule: `heartbeat_5_seconds`
  - purpose: publish MQTT presence heartbeats and keep node freshness visible to operators
- `telemetry`
  - owner: `BackgroundTaskManager.telemetry_loop()`
  - schedule: `telemetry_60_seconds`
  - purpose: refresh baseline runtime telemetry state for operator-facing scheduler visibility
- `operational_mqtt_health`
  - owner: `BackgroundTaskManager.mqtt_health_loop()`
  - schedule:
    - `every_10_seconds` during startup and degraded windows
    - `every_5_minutes` while stable
  - purpose: persist operator-visible MQTT health state on the standard baseline cadence

These baseline tasks now publish structured per-task state under `runtime_task_state.scheduler_task_states`, which is the first persisted scheduler-task-state boundary ahead of the broader standardization work.

That same structured state boundary now also tracks the other modeled recurring tasks in the registry, including:

- onboarding finalize polling
- Gmail status polling
- Gmail fetch windows
- hourly batch classification
- weekly prompt sync
- monthly Core resolve/authorize

Each entry persists the standardized fields:

- `status`
- `enabled`
- `detail`
- `last_started_at`
- `last_completed_at`
- `last_success_at`
- `last_failure_at`
- `next_run_at`
- `last_error`

### Finalize Polling Loop

- Owner: `BackgroundTaskManager.ensure_finalize_polling()` and `poll_finalize_loop()`
- Trigger model: starts when onboarding is pending and a Core onboarding session id exists
- Loop cadence: `ONBOARDING_POLL_INTERVAL_SECONDS`
- Persisted state impact:
  - updates `runtime/state.json`
  - fields affected include `last_poll_at`, `last_finalize_status`, `onboarding_status`, `trust_state`, `trusted_at`, and trust-related runtime fields
- Readiness impact:
  - can transition the node into trusted mode
  - on approval, it triggers MQTT connect and post-trust provider/readiness refresh
- Operator visibility:
  - visible through onboarding status endpoints and UI setup state

### Gmail Status Polling Loop

- Owner: `BackgroundTaskManager.ensure_gmail_status_polling()` and `gmail_status_loop()`
- Trigger model: starts on node startup when `GMAIL_STATUS_POLL_ON_STARTUP=true`
- Loop cadence: `GMAIL_STATUS_POLL_INTERVAL_SECONDS`
- Persisted state impact:
  - refreshes Gmail mailbox status stores under `runtime/providers/gmail/`
  - does not own separate scheduler state in `runtime/state.json`
- Readiness impact:
  - indirect only; refreshed mailbox data informs operational Gmail visibility
- Operator visibility:
  - surfaced through Gmail status API responses and dashboard views

### Gmail Fetch Scheduler Loop

- Owner: `BackgroundTaskManager.ensure_gmail_fetch_polling()` and `gmail_fetch_loop()`
- Trigger model: starts on node startup when `GMAIL_FETCH_POLL_ON_STARTUP=true`
- Loop cadence: wakes on the next minute boundary using `seconds_until_next_minute()`
- Persisted state impact:
  - `runtime/state.json`:
    - `gmail_fetch_scheduler_state`
    - `gmail_last_hour_pipeline_state`
    - hourly batch classification slot fields
  - `runtime/providers/gmail/fetch_schedule_state.json`:
    - persisted per-window Gmail fetch slot execution state
- Readiness impact:
  - indirect only; stale or failed fetch scheduling reduces operational usefulness but does not currently hard-fail node readiness
- Operator visibility:
  - `/api/gmail/status`
  - scheduled task snapshot output
  - fetch warning/error/recovered user notifications via MQTT when state transitions occur

### Gmail Fetch Windows

The Gmail fetch scheduler currently owns three recurring windows:

- `yesterday`
  - schedule: `daily`
  - due slot key: previous local date
  - purpose: previous-day inbox refresh
- `today`
  - schedule: `4_times_a_day`
  - due slot key: `<date>:<6-hour-block>`
  - purpose: current-day inbox refresh
- `last_hour`
  - schedule: `every_5_minutes`
  - due slot key: local timestamp rounded down to the 5-minute bucket
  - purpose: recent-message refresh for local and AI-assisted classification work

### Last-Hour Gmail Pipeline

- Owner: `ProviderManager.run_last_hour_pipeline()`
- Trigger model: runs automatically after a `last_hour` Gmail fetch completes
- Stages:
  - `fetch`
  - `spamhaus`
  - `local_classification`
  - `ai_classification`
- Persisted state impact:
  - updates `state.gmail_last_hour_pipeline_state`
- Readiness impact:
  - none directly
- Operator visibility:
  - surfaced through `/api/gmail/status`
  - visible in runtime UI fetch pipeline status panels

### 5-Minute Gmail Batch Classification

- Owner: `BackgroundTaskManager.run_due_hourly_batch_classification()`
- Trigger model: runs from the Gmail fetch scheduler loop every 5 minutes when the previous batch is not still running
- Slot key model:
  - current local 5-minute bucket ISO timestamp with second and microsecond zeroed
- Persisted state impact:
  - updates `gmail_hourly_batch_classification_slot_key`
  - updates `gmail_hourly_batch_classification_last_run_at`
- Readiness impact:
  - none directly
- Operator visibility:
  - surfaced in scheduled task snapshot output

### 5-Minute Shipment Live Tracking Refresh

- Owner: `BackgroundTaskManager.run_due_shipment_live_tracking_refresh()`
- Trigger model: runs from the shipment live tracking scheduler loop every 5 minutes when Track123 is enabled and configured
- Slot key model:
  - current local 5-minute bucket ISO timestamp with second and microsecond zeroed
- Runtime behavior:
  - calls `NodeService.refresh_all_shipment_live_tracking()`
  - automatically registers recent shipment records that have a tracking number but are not live-tracked yet
  - removes delivered shipments from Track123 after they have been delivered for 30 days, while retaining the local DB record
  - refreshes all shipment records that have live tracking enabled and a tracking number
- Operator visibility:
  - surfaced in scheduled task snapshot output as `shipment_live_tracking_refresh`

### Weekly Runtime Prompt Sync

- Owner: scheduler loop invokes `NodeService._run_weekly_prompt_sync_if_due()`
- Trigger model: weekly if `runtime_prompt_sync_target_api_base_url` is configured
- Slot key model:
  - ISO week string from `RuntimeManager.prompt_sync_weekly_slot_key()`
- Persisted state impact:
  - updates runtime prompt sync slot and last scheduled timestamp fields in `state.json`
- Readiness impact:
  - none directly
- Operator visibility:
  - surfaced in scheduled task snapshot output and runtime task state

### Monthly Core Resolve And Authorize

- Owner: scheduler loop invokes `NodeService._run_due_monthly_runtime_authorize()`
- Trigger model:
  - only on the first local day of the month
  - only during the first 5 minutes of hour `00`
  - only when trust and Core context exist
- Slot key model:
  - `YYYY-MM`
- Persisted state impact:
  - updates monthly authorize slot and last run timestamp fields in `state.json`
- Readiness impact:
  - indirect only; keeps runtime AI authorization fresh
- Operator visibility:
  - surfaced in scheduled task snapshot output

## Persisted Scheduler State

### Node Runtime State

Stored in [state.json](/home/dan/Projects/HexeEmail/runtime/state.json):

- `runtime_task_state.scheduler_task_states`
- `gmail_fetch_scheduler_state`
- `gmail_last_hour_pipeline_state`
- `gmail_hourly_batch_classification_slot_key`
- `gmail_hourly_batch_classification_last_run_at`
- `runtime_prompt_sync_weekly_slot_key`
- `runtime_prompt_sync_last_scheduled_at`
- `runtime_monthly_authorize_slot_key`
- `runtime_monthly_authorize_last_run_at`

### Gmail Provider Schedule State

Stored in [fetch_schedule_state.json](/home/dan/Projects/HexeEmail/runtime/providers/gmail/fetch_schedule_state.json):

- last execution state for `yesterday`
- last execution state for `today`
- last execution state for `last_hour`

This separation is intentional:

- provider-owned fetch slot history lives with the Gmail provider runtime data
- node-owned loop health and operator-visible scheduler status live in `runtime/state.json`

## Operator Visibility

Current operator-facing surfaces:

- `/api/gmail/status`
- scheduled task snapshot in node status responses
- onboarding/setup views for finalize polling outcomes
- MQTT-backed user notifications for Gmail fetch scheduler degradation and recovery

The Scheduled Tasks UI now uses scheduler `kind` as the primary operator-facing category:

- `Node-local`
- `Provider`
- `Core-leased`

The task owner is shown alongside that kind label so operators can distinguish runtime-owned loops from provider-owned or Core-leased work without reading raw ids.

The schedule legend is now normalized from shortest to longest cadence:

- `heartbeat_5_seconds`
- `every_10_seconds`
- `telemetry_60_seconds`
- `every_5_minutes`
- `hourly`
- `4_times_a_day`
- `daily`
- `every_other_day`
- `twice_a_week`
- `weekly`
- `bi_weekly`
- `monthly`
- `on_start`
- `interval_seconds` last when present

Public scheduled-task statuses are normalized to:

- `idle`
- `scheduled`
- `running`
- `healthy`
- `failing`
- `stopped`

Normalization rules:

- internal `active` is exposed as `scheduled`
- internal `inactive` and `pending` are exposed as `idle`
- internal `degraded` is exposed as `failing`
- public Scheduled Tasks responses should not emit those legacy internal values

Scheduled-task status colors now follow the standard:

- `idle` and `stopped`: orange
- `scheduled` and `healthy`: green
- `running`: darker green
- `failing`: red

## Current Boundary

`NodeService` remains the compatibility façade. The actual recurring-work owner is [scheduler.py](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py), and provider-specific execution of Gmail fetches and last-hour processing lives in [providers.py](/home/dan/Projects/HexeEmail/src/node_backend/providers.py).
