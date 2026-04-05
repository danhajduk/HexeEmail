# Provider Boundary

This document makes the node-vs-provider boundary explicit for the email node.

The current implementation splits ownership between node-generic lifecycle code and provider-specific Gmail code. The canonical internal owners are:

- [providers.py](/home/dan/Projects/HexeEmail/src/node_backend/providers.py)
- [registry.py](/home/dan/Projects/HexeEmail/src/providers/registry.py)
- [adapter.py](/home/dan/Projects/HexeEmail/src/providers/gmail/adapter.py)

## Registration Ownership

Provider registration now has one clear path:

- `NodeService` creates `ProviderManager`
- `ProviderManager.build_provider_registry()` constructs `ProviderRegistry`
- `ProviderRegistry.__post_init__()` registers the default Gmail provider exactly once

This removes the previous double-registration shape where Gmail was added both inside `ProviderRegistry` and again inside `NodeService`.

## Node-Owned Responsibilities

These responsibilities are generic to the email node and should stay outside provider adapters:

- onboarding and trust lifecycle
- Core capability declaration
- governance sync and operational readiness
- runtime AI task orchestration
- scheduler loop ownership and operator-facing scheduler state
- MQTT notification delivery
- node-level runtime state persistence in `runtime/state.json`
- route composition and public API shape

Primary code owners:

- [service.py](/home/dan/Projects/HexeEmail/src/service.py)
- [onboarding.py](/home/dan/Projects/HexeEmail/src/node_backend/onboarding.py)
- [governance.py](/home/dan/Projects/HexeEmail/src/node_backend/governance.py)
- [notifications.py](/home/dan/Projects/HexeEmail/src/node_backend/notifications.py)
- [scheduler.py](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py)
- [runtime.py](/home/dan/Projects/HexeEmail/src/node_backend/runtime.py)

## Provider-Owned Responsibilities

These responsibilities are Gmail-specific and belong in the provider adapter and provider runtime subtree:

- OAuth config validation and token exchange
- Gmail account lifecycle and account state transitions
- mailbox fetch queries and Gmail API calls
- mailbox status snapshots
- label discovery and cache state
- stored message persistence
- training dataset assembly and model state
- Spamhaus checks and sender reputation refresh
- shipment reconciliation
- provider-owned fetch slot execution state

Primary code owners:

- [adapter.py](/home/dan/Projects/HexeEmail/src/providers/gmail/adapter.py)
- [runtime.py](/home/dan/Projects/HexeEmail/src/providers/gmail/runtime.py)
- [message_store.py](/home/dan/Projects/HexeEmail/src/providers/gmail/message_store.py)
- [fetch_schedule_store.py](/home/dan/Projects/HexeEmail/src/providers/gmail/fetch_schedule_store.py)

## Boundary Between Node And Gmail

`ProviderManager` is the node-side boundary layer for Gmail.

It owns:

- provider-wide status snapshots
- Gmail account status aggregation for API responses
- invoking Gmail fetches from node routes or scheduler code
- running the node-owned last-hour processing pipeline after Gmail fetches

It does not own:

- low-level Gmail API behavior
- Gmail token persistence
- Gmail fetch slot persistence
- Gmail-specific account state transitions

Those stay inside the Gmail provider package.

## Persistence Boundary

### Node-owned persistence

- [state.json](/home/dan/Projects/HexeEmail/runtime/state.json)
- [operator_config.json](/home/dan/Projects/HexeEmail/runtime/operator_config.json)
- [trust_material.json](/home/dan/Projects/HexeEmail/runtime/trust_material.json)

### Provider-owned persistence

Everything under [runtime/providers/gmail](/home/dan/Projects/HexeEmail/runtime/providers/gmail)

Examples:

- OAuth and account records
- mailbox snapshots
- SQLite message store
- label cache
- Gmail fetch schedule state
- Gmail reports and training artifacts

## Why The Split Matters

This boundary keeps the repo aligned with the Hexe Node standard:

- node-generic lifecycle code does not need to know Gmail internal storage details
- provider-specific logic stays replaceable behind a registry and adapter contract
- scheduler code can operate on provider capabilities without taking ownership of provider internals
- operator docs can describe node runtime state separately from provider runtime data
