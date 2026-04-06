# Scheduler Standard Gap Audit

This document audits the current HexeEmail scheduler and background-task behavior against:

- [background-tasks-and-internal-scheduler-standard.md](/home/dan/Projects/Hexe/docs/standards/Node/background-tasks-and-internal-scheduler-standard.md)

Audit date:

- `2026-04-06`

Primary current implementation:

- [src/node_backend/scheduler.py](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py)
- [docs/scheduler-and-background-tasks.md](/home/dan/Projects/HexeEmail/docs/scheduler-and-background-tasks.md)
- [frontend/src/features/dashboard/ScheduledTasksSection.jsx](/home/dan/Projects/HexeEmail/frontend/src/features/dashboard/ScheduledTasksSection.jsx)

## Current Recurring Work Inventory

Current recurring and long-lived scheduler-relevant work in this node:

- finalize polling loop
- Gmail status polling loop
- Gmail fetch scheduler loop
- Gmail fetch windows:
  - `gmail_fetch_yesterday`
  - `gmail_fetch_today`
  - `gmail_fetch_last_hour`
- last-hour Gmail processing pipeline
- hourly Gmail batch classification
- weekly runtime prompt sync
- monthly Core resolve/authorize

## Current Strengths

Areas where the node is already at least partially aligned with the standard:

- recurring work is not fully invisible; it has a scheduler owner in [scheduler.py](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py)
- several task states are persisted in `runtime/state.json` and provider-owned fetch schedule state files
- scheduled task data is already exposed through bootstrap/status payloads
- scheduled task UI already exists
- startup and shutdown hooks for the main scheduler loops already exist
- task schedules already use operator-readable schedule names such as `daily`, `weekly`, `4_times_a_day`, and `hourly`

## Compliance Gaps

### 1. No explicit registry-backed task model

Standard expectation:

- recurring work should have an explicit task registry with stable identity, ownership, schedule model, and visible task metadata

Current gap:

- [BackgroundTaskManager](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py) hardcodes task rows directly inside `scheduled_tasks_snapshot()`
- there is no registry object or canonical task-definition layer

Impact:

- later task metadata changes require editing snapshot code directly
- ownership and task-kind information are not first-class

Follow-on tasks:

- `Task 327`
- `Task 330`
- `Task 331`

### 2. Mandatory baseline recurring tasks are missing

Standard expectation:

- every node must explicitly model:
  - heartbeat
  - telemetry
  - operational MQTT health

Current gap:

- heartbeat exists operationally through MQTT presence behavior in [src/mqtt.py](/home/dan/Projects/HexeEmail/src/mqtt.py), but it is not modeled as a scheduled task
- telemetry freshness is exposed in status surfaces, but telemetry is not modeled as a scheduler task
- MQTT health is visible, but operational MQTT health is not modeled as a recurring task with task-state visibility

Impact:

- the node fails the standard’s mandatory baseline-task requirement

Follow-on task:

- `Task 328`

### 3. Task visibility model does not match the new standard fields

Standard expectation:

- operator-visible task state should include at minimum:
  - task identity
  - current status
  - last success
  - last failure
  - last error
  - enabled state
- recommended:
  - next run
  - last start
  - last completion
  - schedule detail

Current gap:

- current snapshot rows use:
  - `group`
  - `last_execution_at`
  - `next_execution_at`
  - `last_reason`
  - `last_slot_key`
  - `detail`
- they do not expose:
  - `kind`
  - `enabled`
  - `last_start`
  - `last_completion`
  - `last_success`
  - `last_failure`
  - `last_error`

Impact:

- the UI cannot render the standard column model without backend schema changes

Follow-on tasks:

- `Task 329`
- `Task 333`
- `Task 334`

### 4. Task-state persistence is inconsistent and not normalized per task

Standard expectation:

- recurring task state should be persisted with enough structure for safe restart and operator visibility

Current gap:

- some scheduler state is persisted in `state.json`
- some fetch-window state lives in `runtime/providers/gmail/fetch_schedule_state.json`
- some loops do not have normalized per-task state objects at all
- there is no shared persisted task-state structure spanning every recurring task

Impact:

- restart behavior and UI reporting are inconsistent across tasks

Follow-on tasks:

- `Task 329`
- `Task 330`

### 5. Task ownership and task kind are not explicit enough in operator surfaces

Standard expectation:

- nodes must distinguish:
  - node-local recurring work
  - provider-specific recurring work
  - Core-owned or Core-leased work

Current gap:

- current UI uses `group`, not `kind`
- task rows do not explicitly show owner mapping or scheduling authority
- tasks like monthly authorize blur local scheduling and Core interaction without explicit kind labeling

Impact:

- operators cannot easily tell which tasks are local loops versus provider loops versus Core-facing recurring work

Follow-on tasks:

- `Task 327`
- `Task 331`
- `Task 334`

### 6. Startup and readiness gating are only partially modeled

Standard expectation:

- nodes should define when each task may start and what readiness/trust conditions are required

Current gap:

- startup currently toggles Gmail status polling and Gmail fetch polling from config
- prompt sync and monthly authorize have some inline readiness logic
- there is no unified task-level readiness model or restored task-state-based scheduler startup sequence

Impact:

- readiness behavior is spread across conditionals rather than described by task definition

Follow-on tasks:

- `Task 332`
- `Task 338`

### 7. UI columns and legend do not match the standard

Standard expectation:

- Scheduled Tasks UI should prefer:
  - `Task`
  - `Kind`
  - `Schedule`
  - `Status`
  - `Last Success`
  - `Last Failure`
  - `Next Run`
  - `Last Error`

Current gap:

- [ScheduledTasksSection.jsx](/home/dan/Projects/HexeEmail/frontend/src/features/dashboard/ScheduledTasksSection.jsx) currently shows:
  - `Task`
  - `Group`
  - `Schedule`
  - `Status`
  - `Last Execution`
  - `Next Execution`
  - `Last Reason`
  - `Last Slot`
  - `Detail`

Impact:

- the UI shape is incompatible with the current standard

Follow-on tasks:

- `Task 333`
- `Task 334`
- `Task 335`
- `Task 336`

### 8. Status semantics are not standardized

Standard expectation:

- `idle` and `stopped` orange
- `failing` red
- `running`, `scheduled`, and `healthy` green
- `running` darker green

Current gap:

- current status vocabulary includes values like `active`, `inactive`, and `pending`
- current status-to-tone mapping is not aligned to the newer semantic set

Impact:

- operator UI cannot express the standard lifecycle consistently

Follow-on task:

- `Task 336`

### 9. Regression coverage is not organized around the standard model

Standard expectation:

- tests should cover registry loading, state persistence, baseline recurring tasks, startup/shutdown, and operator rendering

Current gap:

- existing tests cover parts of bootstrap exposure and some Gmail runtime state
- there is no comprehensive regression suite for a registry-backed standard scheduler model because that model does not exist yet

Follow-on task:

- `Task 337`

## Audit Conclusion

Overall compliance state:

- partially compliant

The node already has meaningful recurring-work ownership and operator visibility, but it is still using a pre-standard scheduler model centered on:

- hardcoded snapshot rows
- mixed persistence shapes
- Gmail-specific scheduling assumptions
- missing baseline scheduler tasks
- outdated UI/status fields

The biggest structural gap is the absence of a real scheduler task registry and normalized task-state model. Once that exists, most of the remaining standard-alignment tasks become straightforward follow-on refactors instead of scattered special cases.
