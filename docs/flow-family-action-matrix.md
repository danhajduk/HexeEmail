# Flow-Family Action Matrix

This document lists the current and planned downstream actions for each family, plus the gating conditions that affect them.

Core shared action behavior comes from:

- [actions.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/actions.py)

Family policy comes from each `family.yaml`.

## Shared Gating Rules

Actions are routed only after:

1. Phase 6 produces a decision
2. Phase 7 persistence runs
3. the shared action gate authorizes actions
4. the family routing policy resolves intents
5. family handlers build queue or write results

Current shared action-gate behavior:

- `accept`: actions allowed
- `probation`: actions blocked
- `review_needed`: actions allowed
- `reject`: actions blocked

Additional practical gates:

- provider-facing action handlers depend on provider access if they later become provider-backed
- user notification delivery depends on the `Notifications` switch at the notification send boundary
- AI generation is unrelated to post-decision actions, but affects whether probation templates can exist in the first place

## ORDER

Configured policy sources:

- [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)

Current action intents:

- `store_order_record`
- `update_order_record`
- `user_notification`
- `mark_for_manual_review`
- `attach_tracking_reference`
- `queue_tracking_monitor`

When they appear:

- `store_order_record` for confirmation-style profiles
- `update_order_record` for status-update profiles
- `user_notification` for `accept` and `review_needed`
- `mark_for_manual_review` for `review_needed` and `important_inconsistency`
- `attach_tracking_reference` and `queue_tracking_monitor` when tracking fields satisfy the field rule

Current handler maturity:

- fully implemented family-specific handlers

## ACTION_REQUIRED

Configured policy sources:

- [runtime/flow_families/action_required/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/family.yaml)

Current action intents:

- `store_action_record`
- `user_notification`
- `mark_for_manual_review`
- `mark_high_priority`
- `queue_reminder`

When they appear:

- `store_action_record` and `user_notification` on `accept`
- `user_notification` and `mark_for_manual_review` on `review_needed`
- `mark_high_priority` when diagnostics contain `important_inconsistency`
- `queue_reminder` when diagnostics contain `deadline`

Important nuance:

- policy defines `mark_for_manual_review` for `probation`
- the shared action gate blocks all `probation` actions, so that intent does not currently reach the handler layer

Current handler maturity:

- placeholder queue results only

## FINANCIAL

Configured action intents:

- `store_financial_record`
- `user_notification`
- `mark_for_manual_review`

When they appear:

- record storage on financial update profiles
- notification on `accept` and `review_needed`
- manual-review follow-up on `review_needed`

Current handler maturity:

- placeholder queue results only

## INVOICE

Configured action intents:

- `store_invoice_record`
- `user_notification`
- `mark_for_manual_review`

When they appear:

- record storage on invoice and receipt profiles
- notification on `accept` and `review_needed`
- manual-review follow-up on `review_needed`

Current handler maturity:

- placeholder queue results only

## SECURITY

Configured action intents:

- `store_security_record`
- `user_notification`
- `mark_for_manual_review`

When they appear:

- record storage on security profiles
- notification on `accept` and `review_needed`
- manual-review follow-up on `review_needed`

Current handler maturity:

- placeholder queue results only

## SHIPMENT

Configured action intents:

- `store_shipment_record`
- `user_notification`
- `mark_for_manual_review`

When they appear:

- record storage on shipment profiles
- notification on `accept` and `review_needed`
- manual-review follow-up on `review_needed`

Current handler maturity:

- placeholder queue results only

## Runtime Switch Impact

The most relevant runtime switches are:

- `Clasify`
- `Order`
- `AI Calls`
- `Provider Calls`
- `Notifications`

Practical effect on actions:

- `Notifications` off suppresses actual send behavior even when a family builds a notification request
- `Clasify` off prevents classification-driven family flows from running
- `Order` off disables the ORDER family specifically
- `AI Calls` off disables probation template generation for families that use AI fallback
- `Provider Calls` mainly affects provider fetch behavior rather than already-built downstream action routing

## Current Implementation Reality

Only ORDER currently has real downstream family handlers.

The other families currently prove:

- policy loading
- action authorization
- intent routing
- placeholder queue results

They do not yet prove:

- final domain record persistence beyond shared structured outputs
- family-specific external side effects
