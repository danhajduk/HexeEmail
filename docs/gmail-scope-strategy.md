# Gmail OAuth Scope Strategy

## Purpose

Phase 2 activates Gmail as the first provider for the Email Node. The initial OAuth scope strategy must stay intentionally narrow so the node only requests access that is required for the first classification-first deliverable.

## Initial Scope Set

The current implemented scope set is:

- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.readonly`

Architecture note:

- the long-term classification-first direction will likely require carefully scoped read access later
- when that happens, scope changes should be introduced deliberately and documented as a new architecture step

## Why Send Plus Readonly

- `gmail.send` supports outbound action capability
- `gmail.readonly` supports the lightweight identity and mailbox-profile checks needed after connect
- the pair remains narrower than modify/delete mailbox scopes
- it keeps the activation surface smaller than full mailbox-management access

## Explicitly Deferred Scopes

The following scope categories are intentionally deferred from the first activation path:

- broad mailbox read scopes
- modify or delete scopes
- watch or subscription scopes

Examples of deferred expansion areas include:

- `gmail.modify`
- `https://www.googleapis.com/auth/gmail.metadata`

These are not needed for the Phase 2 activation milestone and would expand the trust boundary prematurely.

## Activation Implications

With `gmail.send` plus `gmail.readonly`:

- Gmail can be linked and validated as an activated provider
- basic account identity/profile checks can complete after callback
- inbox sync, mailbox modification, and watcher setup remain out of scope

## Future Expansion Rule

New Gmail scopes should only be added when:

- a specific node capability requires them
- the capability is documented in the architecture and runbook
- the provider health and declaration logic are updated to match the broader access model
- the classification-first ingest/routing path explicitly needs the additional mailbox access

Scope growth should be additive and justified, not speculative.

## Security Notes

- request the narrowest scope that satisfies the task
- do not request modify/delete scopes for this activation slice
- do not bundle watch or mailbox-management scopes into the first connect flow
- preserve operator visibility into what the node is asking Google to authorize
