# Operations

This document is the repo-level operational source of truth for the Hexe Email Node.

## Canonical local workflow

The intended local operator path is:

1. configure [stack.env](/home/dan/Projects/HexeEmail/scripts/stack.env) or copy from [stack.env.example](/home/dan/Projects/HexeEmail/scripts/stack.env.example)
2. start the stack with [start.sh](/home/dan/Projects/HexeEmail/scripts/start.sh) or directly with [stack-control.sh](/home/dan/Projects/HexeEmail/scripts/stack-control.sh) `start`
3. use [stack-control.sh](/home/dan/Projects/HexeEmail/scripts/stack-control.sh) `status` as the canonical local status path
4. use [restart-stack.sh](/home/dan/Projects/HexeEmail/scripts/restart-stack.sh) for controlled restart behavior
5. treat [status.sh](/home/dan/Projects/HexeEmail/scripts/status.sh) as a compatibility wrapper around `stack-control.sh status`

Canonical local commands:

- `./scripts/stack-control.sh start`
- `./scripts/stack-control.sh status`
- `./scripts/stack-control.sh restart`
- `./scripts/stack-control.sh stop`

Compatibility wrappers:

- `./scripts/start.sh`
- `./scripts/status.sh`
- `./scripts/restart-stack.sh`

## Default local ports

- backend API: `9003`
- frontend UI: `8083`

## Main local entrypoints

- backend health: `GET /health/live`
- backend readiness: `GET /health/ready`
- canonical node status: `GET /api/node/status`
- UI bootstrap: `GET /api/node/bootstrap`

## Gmail operations currently exposed

- fetch status: `GET /api/gmail/status`
- manual fetch windows:
  - `POST /api/gmail/fetch/initial_learning`
  - `POST /api/gmail/fetch/today`
  - `POST /api/gmail/fetch/yesterday`
  - `POST /api/gmail/fetch/last_hour`
- Spamhaus check: `POST /api/gmail/spamhaus/check`
- reputation refresh: `POST /api/gmail/reputation/refresh`
- training routes under `/api/gmail/training`

## Runtime operations currently exposed

- prompt sync: `POST /api/runtime/prompts/sync`
- prompt review: `POST /api/runtime/prompts/review`
- pattern generation: `POST /api/patterns/generate`
- runtime settings: `POST /api/runtime/settings`
- classifier execution routes under `/api/runtime/*`
- task preview/resolve/authorize routes under:
  - `/api/tasks/routing/preview`
  - `/api/core/services/resolve`
  - `/api/core/services/authorize`

Prompt admin notes:

- use `POST /api/runtime/prompts/sync` for normal runtime prompt reconciliation with the AI node
- set `review_due_migration=true` on the sync request when you want the remote AI node to migrate legacy prompt records into the `review_due` lifecycle before reconciliation
- use `POST /api/runtime/prompts/review` when an operator wants to approve or otherwise review a specific remote prompt lifecycle record
- the last review-due migration target and result are persisted in runtime state for operator visibility

## Existing detailed runbooks

- [phase1-runbook.md](/home/dan/Projects/HexeEmail/docs/phase1-runbook.md)
- [phase2-gmail-provider-runbook.md](/home/dan/Projects/HexeEmail/docs/phase2-gmail-provider-runbook.md)
- [gmail-oauth-setup-guide.md](/home/dan/Projects/HexeEmail/docs/gmail-oauth-setup-guide.md)
- [pattern-generation.md](/home/dan/Projects/HexeEmail/docs/pattern-generation.md)

These remain useful implementation references, but this file is now the repo-level starting point.

## systemd notes

The systemd unit templates under [scripts/systemd](/home/dan/Projects/HexeEmail/scripts/systemd) continue to start backend and frontend through [run-from-env.sh](/home/dan/Projects/HexeEmail/scripts/run-from-env.sh). That keeps the command source of truth in `scripts/stack.env`, while `stack-control.sh status` remains the canonical local non-systemd status check.
