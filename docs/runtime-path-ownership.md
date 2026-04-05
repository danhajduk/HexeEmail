# Runtime Path Ownership

This document defines what belongs under `runtime/` today and how each path should be treated operationally.

The goal is to separate:

- restart-safe state
- provider-owned durable data
- logs
- exports and reports
- node-managed caches and generated artifacts
- operator-editable files

## Top-Level Runtime Layout

Current runtime paths observed in this repo:

- `runtime/state.json`
- `runtime/operator_config.json`
- `runtime/trust_material.json`
- `runtime/logs/`
- `runtime/providers/gmail/`
- `runtime/order_templates/`
- `runtime/order_flow_logs/`
- `runtime/exports/`

## Ownership Rules

### Operator-editable files

These may be intentionally edited or replaced by an operator:

- [operator_config.json](/home/dan/Projects/HexeEmail/runtime/operator_config.json)
  - owner: node/operator shared
  - purpose: saved operator inputs such as Core URL, node name, and selected task capabilities
  - restart-safe: yes

### Node-managed restart-safe state

These are written by the node and must survive restart:

- [state.json](/home/dan/Projects/HexeEmail/runtime/state.json)
  - owner: node runtime
  - purpose: node lifecycle state, runtime task state, scheduler state, readiness-related state
  - operator-editable: no
  - restart-safe: yes
- [trust_material.json](/home/dan/Projects/HexeEmail/runtime/trust_material.json)
  - owner: onboarding/trust lifecycle
  - purpose: active trust material received from Core
  - operator-editable: no
  - restart-safe: yes
  - sensitivity: high

### Logs and transient process output

These are node-managed and may be rotated or discarded according to retention policy:

- [runtime/logs](/home/dan/Projects/HexeEmail/runtime/logs)
  - `app.log`
  - `api.log`
  - `providers.log`
  - `core.log`
  - `ai.log`
  - `mqtt.log`
  - rotated `*.log.YYYY-MM-DD_HH` files
  - owner: logging subsystem
  - restart-safe: useful but not required for correctness
  - operator-editable: no

### Provider-owned durable data

Everything under [runtime/providers/gmail](/home/dan/Projects/HexeEmail/runtime/providers/gmail) is Gmail provider-owned runtime data.

Key paths:

- [provider_config.json](/home/dan/Projects/HexeEmail/runtime/providers/gmail/provider_config.json)
  - Gmail OAuth provider config
  - sensitive
- [accounts](/home/dan/Projects/HexeEmail/runtime/providers/gmail/accounts)
  - per-account records and token files
  - sensitive
- [oauth_sessions](/home/dan/Projects/HexeEmail/runtime/providers/gmail/oauth_sessions)
  - pending OAuth session state
  - sensitive, transient but restart-safe while sessions are active
- [oauth_state_secret](/home/dan/Projects/HexeEmail/runtime/providers/gmail/oauth_state_secret)
  - provider-side secret for OAuth state protection
  - sensitive
- [mailbox_status](/home/dan/Projects/HexeEmail/runtime/providers/gmail/mailbox_status)
  - stored mailbox summaries
  - restart-safe
- [messages.sqlite3](/home/dan/Projects/HexeEmail/runtime/providers/gmail/messages.sqlite3)
  - canonical Gmail message database
  - restart-safe
  - sensitive
- [fetch_schedule_state.json](/home/dan/Projects/HexeEmail/runtime/providers/gmail/fetch_schedule_state.json)
  - Gmail fetch slot execution history
  - restart-safe
- [quota_usage.json](/home/dan/Projects/HexeEmail/runtime/providers/gmail/quota_usage.json)
  - Gmail API quota tracking
  - restart-safe
- [labels](/home/dan/Projects/HexeEmail/runtime/providers/gmail/labels)
  - label cache
  - cache-like, node-managed
- [reports](/home/dan/Projects/HexeEmail/runtime/providers/gmail/reports)
  - generated exports and analysis reports
  - durable enough for investigation, but not required for runtime correctness
- [training_model.pkl](/home/dan/Projects/HexeEmail/runtime/providers/gmail/training_model.pkl)
  - local classifier artifact
  - restart-safe
- [training_model_meta.json](/home/dan/Projects/HexeEmail/runtime/providers/gmail/training_model_meta.json)
  - local classifier metadata
  - restart-safe

### Node-managed generated reference data

- [runtime/order_templates](/home/dan/Projects/HexeEmail/runtime/order_templates)
  - deterministic ORDER extraction templates
  - node-managed reference artifacts
  - should normally be source-controlled when curated, but runtime currently hosts the live template set
- [runtime/order_flow_logs](/home/dan/Projects/HexeEmail/runtime/order_flow_logs)
  - generated ORDER flow debug/reference logs
  - not required for runtime correctness
  - operator-reviewable
- [runtime/exports](/home/dan/Projects/HexeEmail/runtime/exports)
  - ad hoc exports and samples
  - not required for runtime correctness

## Practical Classification

### Must survive restart

- `runtime/state.json`
- `runtime/operator_config.json`
- `runtime/trust_material.json`
- `runtime/providers/gmail/messages.sqlite3`
- `runtime/providers/gmail/fetch_schedule_state.json`
- `runtime/providers/gmail/provider_config.json`
- `runtime/providers/gmail/accounts/*`
- `runtime/providers/gmail/oauth_state_secret`
- `runtime/providers/gmail/training_model.pkl`
- `runtime/providers/gmail/training_model_meta.json`

### Safe to regenerate

- `runtime/logs/*`
- `runtime/order_flow_logs/*`
- `runtime/exports/*`
- `runtime/providers/gmail/labels/*`
- many files under `runtime/providers/gmail/reports/*`

### Sensitive and not for casual inspection or sharing

- `runtime/trust_material.json`
- `runtime/providers/gmail/provider_config.json`
- `runtime/providers/gmail/oauth_state_secret`
- `runtime/providers/gmail/accounts/*.token.json`
- `runtime/providers/gmail/oauth_sessions/*`
- `runtime/providers/gmail/messages.sqlite3`

## Node-Managed Versus Operator-Managed

Operator-managed or operator-curated:

- `operator_config.json`
- selected report/export artifacts when intentionally kept

Node-managed:

- `state.json`
- `trust_material.json`
- all provider runtime stores
- all scheduler state
- logs
- caches
- generated ORDER logs

## Documentation Alignment

The repo-level runtime overview in [runtime.md](/home/dan/Projects/HexeEmail/docs/runtime.md) should be read together with this path-level ownership map. This file is the canonical path ownership reference for the current repo layout.
