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
- runtime prompt sync, prompt review, review-due migration, and task execution
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
- prompt admin APIs for sync and review
- services status/restart APIs
- frontend dashboard and setup flow
- runtime settings now gate AI-node calls and provider calls separately

## Runtime notes

Scheduler and background-task ownership is now centered in [scheduler.py](/home/dan/Projects/HexeEmail/src/node_backend/scheduler.py), with provider-specific runtime execution routed through [providers.py](/home/dan/Projects/HexeEmail/src/node_backend/providers.py).

## Prompt lifecycle alignment

The runtime prompt integration is aligned to the Hexe AI Node prompt lifecycle/access policy described in:

- [runtime-prompt-lifecycle-alignment-audit.md](/home/dan/Projects/HexeEmail/docs/runtime-prompt-lifecycle-alignment-audit.md)
- [runtime-prompt-lifecycle-implementation-note.md](/home/dan/Projects/HexeEmail/docs/runtime-prompt-lifecycle-implementation-note.md)

Current behavior:

- local prompt definitions under [runtime/prompts](/home/dan/Projects/HexeEmail/runtime/prompts) carry access-scope, allowed-caller, and review metadata placeholders
- the runtime loads prompt JSON definitions from `PROMPT_DEFINITION_DIR`, which defaults to [runtime/prompts](/home/dan/Projects/HexeEmail/runtime/prompts)
- prompt sync uses `POST /api/prompts/services` only for missing prompts
- existing remote prompt IDs are updated with `PUT /api/prompts/services/{prompt_id}`
- sync reports remote lifecycle state such as `active`, `review_due`, `restricted`, or `probation` instead of collapsing everything into active-versus-retired
- operators can trigger prompt review with `POST /api/runtime/prompts/review`
- operators can trigger legacy remote migration to `review_due` through `POST /api/runtime/prompts/sync` with `review_due_migration=true`
- the runtime state persists the last review-due migration target and result
- direct execution payloads already include caller-aware fields `requested_by`, `service_id`, and `customer_id`
- if a remote runtime denies execution, the node now surfaces lifecycle-aware error text when the response includes prompt-state details

## Capability setup note

Capability setup and trusted startup surfaces continue to expose the node-owned `capability_setup.task_capability_selection` shape through diagnostics and bootstrap responses. This repo did not require a schema change for that part of the AI-node alignment pass, but the prompt lifecycle audit explicitly rechecked it against the upstream startup-resume notes.
