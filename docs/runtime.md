# Runtime

This document is the repo-level runtime behavior source of truth for the Hexe Email Node.

## Runtime ownership today

Primary runtime ownership currently lives in:

- [src/service.py](/home/dan/Projects/HexeEmail/src/service.py)
- provider-specific runtime behavior under [src/providers/gmail/](/home/dan/Projects/HexeEmail/src/providers/gmail/)

## Runtime responsibilities currently implemented

- onboarding start/finalize progression
- trust and readiness state handling
- capability declaration and governance refresh
- task routing preview/resolve/authorize orchestration
- runtime prompt sync and task execution
- Gmail status polling
- Gmail fetch scheduling
- Gmail local classification and related provider operations

## Runtime state and storage

Important runtime-managed files already in use:

- `runtime/state.json`
- `runtime/operator_config.json`
- `runtime/trust_material.json`
- `runtime/providers/gmail/messages.sqlite3`
- `runtime/providers/gmail/*` provider stores, labels, reports, and model artifacts

Path-level ownership and restart-safety rules are documented in:

- [runtime-path-ownership.md](/home/dan/Projects/HexeEmail/docs/runtime-path-ownership.md)
- [security-and-sensitive-state.md](/home/dan/Projects/HexeEmail/docs/security-and-sensitive-state.md)

## Runtime operator visibility

Current operator-visible runtime surfaces include:

- node/bootstrap and status APIs
- runtime execution APIs
- services status/restart APIs
- frontend dashboard and setup flow

## Runtime notes

Scheduler and background-task ownership is now centered in [scheduler.py](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py), with provider-specific runtime execution routed through [providers.py](/home/dan/Projects/HexeEmail/src/node_backend/providers.py).
