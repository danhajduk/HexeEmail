# Synthia Email Node

Synthia Email Node is the Phase 1 email-node runtime for onboarding to Synthia Core, persisting trust state locally, and establishing the operational MQTT connection used after approval.

Phase 1 intentionally focuses on node bootstrap and trust activation:

- provider-neutral node identity (`email-node`)
- operator-mediated onboarding to Core
- restart-safe local state persistence
- structured logging and status endpoints
- provider abstraction scaffolding for Gmail, SMTP, IMAP, and Graph

See [docs/email-node-architecture.md](/home/dan/Projects/SynthiaEmail/docs/email-node-architecture.md) for the Phase 1 trust/runtime baseline, [docs/email-node-phase2-provider-activation.md](/home/dan/Projects/SynthiaEmail/docs/email-node-phase2-provider-activation.md) for the Phase 2 provider design, [docs/phase1-runbook.md](/home/dan/Projects/SynthiaEmail/docs/phase1-runbook.md) for local onboarding, and [docs/phase2-gmail-provider-runbook.md](/home/dan/Projects/SynthiaEmail/docs/phase2-gmail-provider-runbook.md) for Gmail activation.

The local node API runs on port `9002` by default. The React onboarding UI runs on port `8083` and reuses the Core theme tokens/CSS direction so the operator experience stays visually aligned with Synthia Core.
