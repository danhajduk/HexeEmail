# Flow-Family Terminal Outcomes

This document explains the shared terminal outcomes used across all flow families.

Primary shared contract:

- [decision.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/decision.py)
- [persistence.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/persistence.py)

## Shared Decisions

Current shared decisions are:

- `accept`
- `probation`
- `review_needed`
- `reject`

## Accept

Meaning:

- active extraction succeeded at high confidence

Decision flags:

- persists structured result
- allows downstream actions
- does not require manual review

Persistence:

- written as trust level `trusted`

Typical action behavior:

- family action routing can proceed
- notifications may be built
- record-writing actions may be built

## Probation

Meaning:

- the structured result exists, but it is medium-confidence or came from a probation template

Decision flags:

- persists structured result
- blocks downstream actions
- requires manual review

Persistence:

- written as trust level `partial`

Typical action behavior:

- no downstream actions pass the shared action gate
- the result is retained for review and future promotion analysis

Typical causes:

- active extraction confidence in the family’s medium band
- low-confidence fallback from a probation template

## Review Needed

Meaning:

- the system did not safely reach a trusted result, but the mail should still be surfaced for review

Decision flags:

- persists structured result shell
- allows review-facing downstream actions
- requires manual review

Persistence:

- written as trust level `review_needed`

Typical action behavior:

- user notification may still be built
- manual-review markers may still be built

Typical causes:

- no structured extraction
- hard validation failure
- low-confidence active extraction

Important implementation detail:

- the current shared decision engine maps both missing extraction and hard validation failures to `review_needed`
- this is why failed family flows can still surface in the review-needed bucket instead of disappearing

## Reject

Meaning:

- the flow should stop with no persisted structured result

Decision flags:

- persistence blocked
- downstream actions blocked
- manual review not automatically surfaced through the shared persistence path

Persistence:

- no persisted structured output

Typical causes:

- an explicit family or future policy chooses a hard stop

Current note:

- after the cross-family `review_needed` work, most unresolved family failures now prefer `review_needed` over silent rejection

## Persistence Outcomes

The persistence layer currently emits one of these trust buckets:

- `trusted`
- `partial`
- `review_needed`

Or blocks persistence entirely with:

- `decision_blocked:<reason>`

This means a flow can end in one of these operator-visible states:

- trusted persisted output
- partial persisted output
- review-needed persisted output
- no persisted output

## Action Outcomes

After persistence, the action system can end in one of these broad states:

- actions allowed and routed
- actions blocked by decision
- actions allowed but no matching intents

Because action authorization is shared, these patterns apply across families:

- `accept` usually means actions may run
- `probation` means actions are blocked
- `review_needed` means review-facing actions may still run
- `reject` means actions are blocked

## User Review Handoff

The current user-review handoff is only partially implemented.

What exists now:

- `review_needed` persisted outputs
- manual-review intents in action policies
- notification request construction in the families that define it

What is still planned:

- the actual user-review workflow after a `review_needed` result
- operator or user review resolution handling
- family-specific remediation paths after review

So the current state is:

- the system can mark a message as `review_needed`
- persist it
- and surface review-oriented intents
- but the end-user review experience is still a later task batch
