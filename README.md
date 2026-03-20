# Synthia Email Node

Synthia Email Node is a classification-first email ingress and routing node for Synthia. It onboards to Synthia Core as `email-node`, persists local trust state, activates provider integrations such as Gmail, and delegates AI work to the AI Node instead of performing local inference.

Current phases:

- Phase 1: Core trust onboarding, trust persistence, operational MQTT, local status/UI
- Phase 2: Gmail provider activation, capability declaration, governance sync, readiness evaluation

Architecture and runbooks:

- [docs/email-node-architecture.md](/home/dan/Projects/SynthiaEmail/docs/email-node-architecture.md)
- [docs/email-node-phase2-provider-activation.md](/home/dan/Projects/SynthiaEmail/docs/email-node-phase2-provider-activation.md)
- [docs/phase1-runbook.md](/home/dan/Projects/SynthiaEmail/docs/phase1-runbook.md)
- [docs/phase2-gmail-provider-runbook.md](/home/dan/Projects/SynthiaEmail/docs/phase2-gmail-provider-runbook.md)
- [docs/gmail-oauth-setup-guide.md](/home/dan/Projects/SynthiaEmail/docs/gmail-oauth-setup-guide.md)

Local defaults today:

- node API: `9003`
- onboarding UI: `8083`
- Gmail provider setup is available from the UI via `Setup Provider`

For Gmail OAuth documentation, the standardized Web Application callback reference is:

- `http://localhost:9003/providers/gmail/oauth/callback`
