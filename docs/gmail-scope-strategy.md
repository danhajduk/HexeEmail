# Gmail OAuth Scope Strategy

## Purpose

Phase 2 activates Gmail as the first provider for the Email Node. The initial OAuth scope strategy must stay intentionally narrow so the node only requests access that is required for the first deliverable.

## Initial Scope Set

The minimum required scope for first activation is:

- `https://www.googleapis.com/auth/gmail.send`

This scope is the recommended first slice because it enables outbound email capability without immediately requesting broad mailbox access.

## Why `gmail.send` First

- it supports the first practical Gmail capability we want to unlock
- it avoids unnecessary read access to mailbox contents
- it reduces operator concern during OAuth consent review
- it keeps the activation surface aligned with least-privilege design
- it gives the node a clean path to declare Gmail support without over-claiming inbox control

## Explicitly Deferred Scopes

The following scope categories are intentionally deferred from the first activation path:

- broad mailbox read scopes
- modify or delete scopes
- watch or subscription scopes

Examples of deferred expansion areas include:

- `gmail.readonly`
- `gmail.modify`
- `https://www.googleapis.com/auth/gmail.metadata`

These are not needed for the Phase 2 activation milestone and would expand the trust boundary prematurely.

## Activation Implications

With `gmail.send` only:

- Gmail can be linked and validated as an activated provider
- outbound-provider capability can be declared later in a controlled way
- inbox sync, mailbox inspection, and watcher setup remain out of scope

## Future Expansion Rule

New Gmail scopes should only be added when:

- a specific node capability requires them
- the capability is documented in the architecture and runbook
- the provider health and declaration logic are updated to match the broader access model

Scope growth should be additive and justified, not speculative.

## Security Notes

- request the narrowest scope that satisfies the task
- do not request read scopes for send-only activation
- do not bundle watch or mailbox-management scopes into the first connect flow
- preserve operator visibility into what the node is asking Google to authorize
