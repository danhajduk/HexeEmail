# Email Node Phase 2 Provider Activation

## Purpose

Phase 2 extends the trusted Email Node runtime from basic node onboarding into provider activation, with Gmail as the first production-facing provider integration.

The goal of this phase is to:

- activate Gmail as the first supported provider ingress
- keep the provider model extensible for future providers such as SMTP, IMAP, and Graph
- integrate provider activation with Core capability declaration so Core can understand what this node can actually do
- keep the node classification-first so AI work is delegated to AI Node instead of executed locally

## Phase 2 Scope

Phase 2 includes:

- provider runtime domain models that stay provider-neutral
- provider registry and adapter lookup
- Gmail provider static configuration
- Gmail OAuth Web Application connect flow for operator-mediated account activation
- Gmail token storage and runtime account records
- Gmail provider health validation
- capability declaration updates that reflect provider readiness
- governance fetch and local governance synchronization required for provider-aware readiness
- normalized ingress and routing-oriented capability framing

## Out Of Scope

Phase 2 does not implement:

- full mailbox client behavior
- local AI execution
- embedded mailbox management UI
- out-of-band Gmail auth flows
- inbox synchronization
- Gmail watch or subscription setup
- outbound queueing or durable send pipelines
- advanced policy enforcement
- multi-account orchestration beyond a design-compatible foundation

## Phase 2 Runtime Goal

At the end of Phase 2, the Email Node should still onboard to Core as a trusted `email-node`, then activate Gmail as an internal provider capability.

That means the node has two distinct lifecycle layers:

1. node trust lifecycle
2. provider activation lifecycle

Phase 1 established the trust lifecycle. Phase 2 adds the first provider lifecycle on top of it without changing the node identity model.

## Architectural Principles

- the node remains provider-neutral at the root runtime level
- the node is classification-first: email ingress, normalization, routing, and automation orchestration come before user-facing mailbox behaviors
- providers plug into the node through a shared adapter contract
- provider state is local-first and restart-safe
- capability declaration is based on actual provider readiness, not static intent
- governance data is treated as Core-owned and consumed, not redefined by the node
- Gmail-specific code lives in a Gmail-specific boundary and does not leak into provider-neutral interfaces
- AI-dependent work is delegated to AI Node rather than performed inside the Email Node runtime

## Phase 2 Flow

1. The node starts in a trusted state from Phase 1 onboarding.
2. The provider registry loads supported adapters and exposes Gmail as the first available provider.
3. The operator configures Gmail static OAuth settings for the node using a Google OAuth Web Application client.
4. The operator starts a Gmail connect flow for a target account.
5. The node generates and persists an OAuth session state locally, then returns a Google Authorization Code flow URL.
6. Google redirects back to the Email Node callback endpoint with OAuth result parameters.
7. The Email Node validates the callback state, exchanges the authorization code server-side, and stores the resulting refresh token locally and securely.
8. The node refreshes access tokens as needed from the stored refresh token.
9. The node performs a lightweight Gmail identity and health validation to confirm the account linkage.
10. The node updates its provider account record and provider activation summary.
11. The node updates capability declaration data and syncs governance-dependent readiness state with Core.

Default development callback reference:

- `http://localhost:9003/providers/gmail/oauth/callback`

## Component Boundaries

### Provider Models

Shared provider models define:

- provider identity
- provider state
- account-level state
- validation results
- health summaries
- activation summaries

These models must not assume Gmail-only terminology so later providers can reuse them.

### Provider Registry

The registry is responsible for:

- registering provider adapters
- exposing lookup by provider id
- listing supported providers

The registry must stay independent from Core capability submission logic. Core-facing updates should consume provider state rather than own the provider registration system.

### Gmail Adapter Boundary

The Gmail adapter owns:

- Gmail static config interpretation
- OAuth state/session handling
- server-side authorization code exchange
- refresh token storage
- access token refresh
- Gmail account identity probing
- Gmail provider health checks

The Gmail adapter does not own:

- node trust onboarding
- Core governance semantics
- generic node readiness policy outside Gmail-specific validation inputs
- AI inference or classification execution

## Filesystem Layout

Phase 2 introduces provider runtime state under the existing runtime directory:

- `runtime/providers/gmail/`
- `runtime/providers/gmail/provider_config.json`
- `runtime/providers/gmail/accounts/`
- `runtime/providers/gmail/oauth_sessions/`

Sensitive files such as token records and secret-bearing configuration references should use restricted file permissions where the host platform allows it.

## Capability Declaration Integration

Capability declaration must become provider-aware in Phase 2.

The node should declare:

- support for Gmail as an available ingress provider when the adapter is present
- activation state only when Gmail configuration, token acquisition, and account validation succeed
- task families aligned with email ingress, routing, and automation orchestration

This avoids advertising provider capability before the node can actually execute it.

## Governance Sync Role

Governance remains Core-owned. The Email Node should fetch and persist the relevant governance snapshot needed to evaluate whether the current trusted node and activated provider state are operationally acceptable.

Phase 2 governance sync is limited to:

- fetching governance data from Core
- persisting a local snapshot
- exposing governance presence and sync status into readiness evaluation

It does not redefine governance policy or alter Core templates.

## Readiness Model

By the end of Phase 2, readiness should be evaluated across:

- node trust established
- provider configured through the Web Application OAuth flow
- provider account linked
- provider health validated
- capability declaration current
- governance snapshot present and in sync
- classification-oriented ingress path ready for AI delegation

This is broader than Phase 1 readiness, which only needed trust activation and operational MQTT connection.

## Security Notes

- do not log raw OAuth tokens
- keep OAuth state single-use and expiring
- separate static provider config from runtime token storage
- store tokens per account to preserve future multi-account expansion
- treat client secret handling as reference-based where possible rather than embedding raw secret values in generic config
- use Google OAuth Web Application credentials, not desktop/native credentials

## Extensibility Notes

Although Gmail is the first provider, the Phase 2 design must keep room for:

- SMTP account activation and send validation
- IMAP account linkage and mailbox health
- Graph-based enterprise provider support

That means provider-neutral models and registry interfaces are part of the phase deliverable, not a later refactor.

## Delivery Boundary

Phase 2 is complete when:

- Gmail can be configured and connected through a node-owned OAuth flow
- Gmail tokens are stored safely and validated
- provider state is visible through node APIs
- capability data reflects Gmail activation
- governance state is fetched and incorporated into readiness
- normalized email ingress path is available
- AI delegation boundary is documented and preserved

## Migration Notes

The current Phase 2 docs supersede earlier looser wording in these areas:

- Gmail authentication is standardized on Google OAuth Web Application flow
- the Email Node owns the Gmail callback, token exchange, and refresh-token storage
- Core trust onboarding is separate from Gmail provider authorization
- Gmail is treated as provider ingress into a classification-first node
- AI work is delegated to AI Node instead of executed locally in Email Node

Phase 2 is not complete merely because Gmail OAuth begins. Provider activation must reach a validated and declared operational state.
