# Runtime Prompt Lifecycle Implementation Note

This note records the email-node implementation changes made to align local runtime prompt behavior with the newer Hexe AI Node prompt lifecycle/access policy.

Upstream reference sources:

- `/home/dan/Projects/HexeAiNode/docs/ai-node/prompt-lifecycle-and-access-policy.md`
- `/home/dan/Projects/HexeAiNode/docs/api-map.md`
- `/home/dan/Projects/HexeAiNode/docs/ai-node-golden-mismatch-prompt-service-phase2.md`
- `/home/dan/Projects/HexeAiNode/docs/ai-node-golden-mismatch-startup-resume-and-capability-setup.md`

Implemented in this repo:

- local runtime prompt JSON definitions now carry access-scope, allowed-caller, and review metadata placeholders
- runtime prompt sync uses:
  - `POST /api/prompts/services` for missing remote prompts
  - `PUT /api/prompts/services/{prompt_id}` for updating existing prompt records
  - `POST /api/prompts/services/migrations/review-due` when the operator requests review-due migration
- runtime prompt admin now exposes `POST /api/runtime/prompts/review`, which forwards to `POST /api/prompts/services/{prompt_id}/review`
- sync results now preserve and report remote lifecycle state instead of assuming a simple active-versus-retired model
- runtime state now stores the last review-due migration target and result for operator visibility
- direct AI execution payloads continue to send caller-aware fields `requested_by`, `service_id`, and `customer_id`
- runtime execution now surfaces clearer denial text when the AI node returns lifecycle-aware access errors

Non-code alignment notes:

- the existing email-node execution payloads already matched the caller-aware authorize/access requirement, so this pass verified and preserved that behavior
- the existing capability setup and trusted startup status surfaces were rechecked against the AI-node startup-resume notes and did not require a local schema change in this repo
