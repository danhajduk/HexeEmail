# Hexe Email Node

Hexe Email Node is a classification-first email ingress and routing node for Hexe. It onboards to Hexe Core as `email-node`, persists local trust state, activates provider integrations such as Gmail, and delegates AI work to the AI Node instead of performing local inference.

Current phases:

- Phase 1: Core trust onboarding, trust persistence, operational MQTT, local status/UI
- Phase 2: Gmail provider activation, capability declaration, governance sync, readiness evaluation

Architecture and runbooks:

- [docs/email-node-architecture.md](docs/email-node-architecture.md)
- [docs/email-node-phase2-provider-activation.md](docs/email-node-phase2-provider-activation.md)
- [docs/phase1-runbook.md](docs/phase1-runbook.md)
- [docs/phase2-gmail-provider-runbook.md](docs/phase2-gmail-provider-runbook.md)
- [docs/gmail-oauth-setup-guide.md](docs/gmail-oauth-setup-guide.md)

Local defaults today:

- node API: `9003`
- onboarding UI: `8083`
- Gmail provider setup is available from the UI via `Setup Provider`

Gmail provider activation uses a Google `Web application` client with a public HTTPS callback on the node, typically through a Cloudflare Tunnel hostname such as:

- `https://email-node.example.com/providers/gmail/oauth/callback`
