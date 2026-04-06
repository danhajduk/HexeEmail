# ORDER Family Reference

This document is the detailed implementation reference for the `order` flow family.

Primary runtime entrypoints:

- [src/email_node/pipeline/order_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_flow.py)
- [src/email_node/flow_families/order/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/runtime.py)
- [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)

## Purpose

The ORDER family is the most complete family in the shared pipeline system.

It is responsible for:

- identifying transactional order-style emails
- resolving an order profile
- extracting structured fields through deterministic templates
- using AI-backed probation templates when active templates are missing
- persisting trusted, partial, or review-needed outputs
- emitting downstream order-related actions

## Current ORDER Profiles

The current taxonomy in [family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml) includes:

- `amazon_order_confirmation`
- `amazon_order_status_update`
- `amazon_order_cancellation`
- `pickup_ready_notification`
- `curbside_pickup_order`
- `reservation_confirmation`
- `upcoming_order_notice`
- `generic_order_confirmation`
- `generic_order_status_update`
- `generic_order_cancellation`
- `ride_receipt`
- `ride_cancellation`

Known vendor hints currently include:

- `amazon.com`
- `dutchie.com`
- `walmart.com`
- `recreation.gov`
- `edenredbenefits.com`

## Phase 2 Behavior

ORDER uses the shared scrub engine with ORDER-specific heuristics.

Source:

- [src/providers/gmail/order_phase2.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase2.py)
- [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)

Key ORDER scrub goals:

- keep order identifiers, totals, quantity, arrival language, reservation language, and action links
- drop promotional chrome and footer noise
- classify important links into types such as tracking, order action, account, and document action

## Phase 3 Detection

ORDER profile detection uses:

- family YAML rules in [family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)
- compatibility override rules in [order_profile_rules.json](/home/dan/Projects/HexeEmail/runtime/order_profile_rules.json)
- shared scoring mechanics through [profile_detector.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/profile_detector.py)

Important ORDER signals include:

- confirmation language
- shipment and delivery language
- cancellation language
- reservation language
- curbside and pickup language
- ride receipt language

Special handling already exists for ride-style order mail:

- `ride_receipt`
- `ride_cancellation`

That handling prevents generic `cancel + pickup` conflicts from incorrectly downgrading ride emails when the message uses `Pickup:` and `Drop-off:` as trip fields rather than retail pickup semantics.

## Phase 4 Extraction

ORDER Phase 4 uses deterministic template execution through:

- [src/providers/gmail/order_phase4.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase4.py)
- [src/providers/gmail/order_template_registry.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_template_registry.py)
- [runtime/flow_families/order/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/order/templates)

The engine supports:

- active template lookup
- family validation policy
- confidence scoring
- AI handoff payload generation when active templates are missing

Current deterministic extraction methods are shared with the template engine and include the ORDER template method set used by the runtime template registry.

## ORDER Probation Flow

ORDER has the most complete probation implementation in the repo.

Probation runtime locations:

- [runtime/flow_families/order/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/templates)
- [runtime/flow_families/order/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/state)
- [runtime/flow_families/order/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/evaluations)
- [runtime/flow_families/order/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/shadow)

Probation behavior in [runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/runtime.py):

- unresolved or failed Phase 4 results may trigger AI template generation
- existing probation templates are reused before generating a new one
- probation templates are evaluated against live mails
- successful probation templates can be applied back as low-confidence Phase 4 partial results
- active-template runs can also shadow-evaluate an existing probation template
- probation state is promotion-aware through shared probation metrics and promotion policy

Current gating for probation generation:

- `Check Orders` must be enabled
- AI calls must be enabled
- a pattern-generation callback must be wired

## Decisioning

ORDER uses the shared decision engine through:

- [src/email_node/pipeline/order_decision_engine.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_decision_engine.py)
- [src/email_node/flow_families/order/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/decision.py)

In practice:

- high-confidence active template results become `accept`
- medium-confidence active template results become `probation`
- probation-applied templates remain `probation`
- low-confidence or missing structured results become `review_needed`
- hard validation failures become `review_needed`

## Persistence

ORDER persistence is implemented through:

- [src/email_node/pipeline/order_output_handler.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_output_handler.py)
- shared persistence in [persistence.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/persistence.py)

Practical persisted trust levels:

- `trusted` for accepted outputs
- `partial` for probation outputs
- `review_needed` for unresolved but review-worthy outputs

Compatibility note:

ORDER still preserves legacy runtime compatibility in [runtime/order_outputs](/home/dan/Projects/HexeEmail/runtime/order_outputs), while the shared family model writes under [runtime/flow_families/order/outputs](/home/dan/Projects/HexeEmail/runtime/flow_families/order/outputs).

## Downstream Actions

ORDER is the only family with real downstream integrations today.

Action policy source:

- [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)

Concrete handlers:

- order record writing via [src/email_node/orders/order_record_service.py](/home/dan/Projects/HexeEmail/src/email_node/orders/order_record_service.py)
- user notification request building via [src/email_node/actions/user_notification_handler.py](/home/dan/Projects/HexeEmail/src/email_node/actions/user_notification_handler.py)
- tracking monitor request building via [src/email_node/actions/tracking_monitor_handler.py](/home/dan/Projects/HexeEmail/src/email_node/actions/tracking_monitor_handler.py)

Configured action intents include:

- `store_order_record`
- `update_order_record`
- `user_notification`
- `mark_for_manual_review`
- `attach_tracking_reference`
- `queue_tracking_monitor`

Routing sources:

- profile-based intents for confirmation and status profiles
- decision-based intents for `accept` and `review_needed`
- diagnostic token intents for `important_inconsistency`
- field rules that require tracking number plus supporting fields

Important current behavior:

- `probation` outputs persist but do not run downstream actions
- `review_needed` outputs can still emit review-facing actions

## Runtime Switch Interaction

Relevant runtime switches:

- `AI Calls`
- `Provider Calls`
- `Notifications`
- `Clasify`
- `Order`

ORDER-specific effects:

- if `Order` is off, the ORDER flow is skipped
- if `Clasify` is off, ORDER flow also does not run because ORDER depends on classification-enabled analysis
- if `AI Calls` is off, active deterministic templates still run, but AI probation generation is skipped
- if `Notifications` is off, notification requests are built but not sent at the notification boundary

## Current Strengths

- strong live coverage for common order flows
- active template support
- AI probation generation and reuse
- real downstream handlers
- broad diagnostics and ad hoc reporting

## Current Gaps

- unknown profiles still depend on probation generation or manual review
- some generic confirmations can resolve only through low-confidence probation templates
- ORDER-specific compatibility paths still exist because migration is not fully legacy-free yet

## Related Documents

- [Email Processing Pipeline (ORDER Flow).md](/home/dan/Projects/HexeEmail/docs/Email%20Processing%20Pipeline%20%28ORDER%20Flow%29.md)
- [order-phase3-profile-detection.md](/home/dan/Projects/HexeEmail/docs/order-phase3-profile-detection.md)
- [order-phase4-template-extraction.md](/home/dan/Projects/HexeEmail/docs/order-phase4-template-extraction.md)
- [order-pattern-probation-lifecycle.md](/home/dan/Projects/HexeEmail/docs/order-pattern-probation-lifecycle.md)
