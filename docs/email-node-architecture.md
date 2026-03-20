# Email Node Architecture

## Purpose

The Synthia Email Node is a provider-neutral edge/runtime service that onboards to Synthia Core as an `email-node`, persists trust material locally, and establishes an operational MQTT connection after approval.

## Phase 1 Scope

Phase 1 covers:

- local runtime bootstrap and validated configuration
- operator-mediated onboarding session creation
- approval URL surfacing for a headless operator flow
- finalize polling and trust activation persistence
- restart-safe resume behavior
- MQTT operational connectivity and presence publication
- local health and status APIs
- provider abstraction interfaces and a Gmail placeholder adapter

## Out Of Scope

Phase 1 does not implement:

- Gmail OAuth
- Gmail API operations
- SMTP or IMAP send/receive flows
- mailbox synchronization
- Core-side capability activation beyond trust establishment
- production secret vault integration

## Onboarding Flow To Core

1. The node starts with validated environment configuration.
2. If trust has not been established, it creates `POST /api/system/nodes/onboarding/sessions`.
3. Core returns a persisted `session_id`, `approval_url`, `expires_at`, and finalize route metadata.
4. The node prints and logs the approval URL so an operator can complete approval in Core.
5. The node polls the finalize endpoint until Core returns a terminal onboarding state.
6. On approval, the node persists trust material locally, activates the MQTT operational connection, and transitions into trusted runtime behavior.

## Provider Abstraction Boundary

Provider-specific logic lives under `src/providers/`.

- provider models define the stable provider-neutral contract
- provider registry exposes configured adapters
- provider adapters are responsible for provider-specific health and future send/receive operations

Gmail is the first planned provider, but the root runtime remains provider-neutral. The node identity is `email-node`, not `gmail-node`, so later SMTP, IMAP, Graph, or other providers can share the same onboarding and operational trust path.

## Identity Strategy

- canonical `node_type` is `email-node`
- `node_name` is operator-assigned and unique within the deployment context
- `node_nonce` binds finalize calls to the local runtime instance during onboarding
- after approval, Core-issued `node_id` becomes the stable trusted identity
