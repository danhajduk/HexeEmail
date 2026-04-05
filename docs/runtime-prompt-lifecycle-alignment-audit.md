# Runtime Prompt Lifecycle Alignment Audit

Source documents reviewed:

- `/home/dan/Projects/HexeAiNode/docs/ai-node/prompt-lifecycle-and-access-policy.md`
- `/home/dan/Projects/HexeAiNode/docs/api-map.md`
- `/home/dan/Projects/HexeAiNode/docs/ai-node-golden-mismatch-prompt-service-phase2.md`
- `/home/dan/Projects/HexeAiNode/docs/ai-node-golden-mismatch-startup-resume-and-capability-setup.md`

Date reviewed: 2026-04-04

## Current Email Node Behavior

Current local prompt/runtime behavior in this repo:

- local prompt definitions are stored under [runtime/prompts](/home/dan/Projects/HexeEmail/runtime/prompts)
- prompt sync uses:
  - `GET /api/prompts/services`
  - `GET /api/prompts/services/{prompt_id}`
  - `POST /api/prompts/services`
  - `POST /api/prompts/services/{prompt_id}/lifecycle`
- an outdated remote prompt is retired and re-registered rather than updated in place
- remote prompt status is effectively flattened to:
  - missing
  - active and current
  - not-current, then retire and replace
- no local support exists yet for:
  - `POST /api/prompts/services/{prompt_id}/review`
  - `POST /api/prompts/services/migrations/review-due`
  - `review_due` as a first-class executable lifecycle state
  - explicit prompt access-scope metadata
  - persisted review migration state/reporting

## Contract Deltas From Hexe AI Node

### Prompt lifecycle

The AI node contract now treats the following lifecycle states as meaningful:

- `draft`
- `probation`
- `active`
- `review_due`
- `restricted`
- `suspended`
- `retired`
- `archived`

Important delta for this repo:

- `review_due` is executable but operator-visible
- the email node must not treat every non-`active` state as equivalent

### Canonical prompt update path

The AI node contract now defines:

- `PUT /api/prompts/services/{prompt_id}`

as the canonical path for existing prompt updates.

Important delta for this repo:

- retire-and-reregister must stop being the default update flow

### Review and migration routes

The AI node canonical prompt route family now includes:

- `POST /api/prompts/services/{prompt_id}/review`
- `POST /api/prompts/services/migrations/review-due`

Important delta for this repo:

- the email node currently cannot call these routes
- no local admin/runtime state tracks review migration activity

### Access policy

The AI node policy adds explicit prompt access behavior beyond `privacy_class`.

Important delta for this repo:

- prompt definitions here need to carry explicit access-scope and allowed-caller metadata placeholders
- runtime authorization and direct execution requests should send caller-aware fields consistently

### Lifecycle/status follow-through

The AI node lifecycle mismatch report for startup resume and capability setup is already mostly aligned in this repo.

Verified local alignment already present:

- `capability_setup.task_capability_selection` is present
- `task_capability_selection_valid` is present in readiness flags
- trusted resume and operational readiness behavior already exist in the local runtime

Remaining work:

- make that alignment explicit in local docs/tests while the prompt/runtime contract is being updated

## Implementation Direction

The required implementation changes for the email node are:

1. extend prompt definition metadata
2. add update/review/migration API support in the runtime integration layer
3. make prompt sync lifecycle-aware
4. persist migration/reporting state locally
5. treat `review_due` as executable but visible
6. update tests and docs to the new contract
