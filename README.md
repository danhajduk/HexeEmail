# Synthia Email Node

Synthia Email Node is the Phase 1 email-node runtime for onboarding to Synthia Core, persisting trust state locally, and establishing the operational MQTT connection used after approval.

Phase 1 intentionally focuses on node bootstrap and trust activation:

- provider-neutral node identity (`email-node`)
- operator-mediated onboarding to Core
- restart-safe local state persistence
- structured logging and status endpoints
- provider abstraction scaffolding for Gmail, SMTP, IMAP, and Graph

See [docs/email-node-architecture.md](/home/dan/Projects/SynthiaEmail/docs/email-node-architecture.md) for the current architecture and [docs/phase1-runbook.md](/home/dan/Projects/SynthiaEmail/docs/phase1-runbook.md) for local operation.
