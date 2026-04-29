# ACTION_REQUIRED Family Reference

This document is the detailed implementation reference for the `action_required` flow family.

Primary runtime entrypoints:

- [src/email_node/pipeline/action_required_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/action_required_flow.py)
- [src/email_node/flow_families/action_required/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/runtime.py)
- [runtime/flow_families/action_required/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/family.yaml)

## Purpose

The ACTION_REQUIRED family is for mails where the system should detect an actionable operational or account task rather than an order lifecycle.

Examples include:

- payment due or payment method update
- account verification
- verification code delivery
- security or service issue follow-up
- document signature or document availability notices
- appointment preparation or check-in reminders

## Current ACTION_REQUIRED Profiles

The live taxonomy includes:

- `subscription_expiring`
- `benefit_order_update_required`
- `appointment_preparation_required`
- `appointment_scheduling_required`
- `payment_due`
- `payment_method_update_required`
- `subscription_payment_failed`
- `application_completion_required`
- `account_verification_required`
- `verification_code_required`
- `account_retention_required`
- `security_alert_action_required`
- `site_issue_action_required`
- `service_issue_action_required`
- `document_signature_required`
- `document_available_action_required`
- `pickup_ready_action_required`
- `travel_check_in_required`
- `benefit_expiring`
- `generic_action_required`

Known vendor hints currently include:

- `capitalone.com`
- `creditkarma.com`
- `edenredbenefits.com`
- `alaskaair.com`
- `walgreens.com`
- `tripit.com`
- `aftership.com`
- `intuit.com`
- `google.com`
- `meetaxle.com`

## Phase 2 Behavior

ACTION_REQUIRED uses the shared scrub engine with family-specific heuristics.

Source:

- [runtime/flow_families/action_required/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/family.yaml)
- [src/email_node/flow_families/action_required/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/runtime.py)

Current Phase 2 goals:

- preserve action verbs like verify, confirm, sign, pay, resolve, and reset
- keep deadline-like and security-style signals
- retain account and document action links

Current limitation:

- ACTION_REQUIRED scrub behavior is still built on the shared transactional scrub model, which was originally shaped around ORDER mail
- some real-world action-required emails still fail to deliver usable Phase 3 input because scrub completeness remains too ORDER-biased

## Phase 3 Detection

ACTION_REQUIRED Phase 3 uses shared detector mechanics plus a family-specific taxonomy.

It detects signals for:

- subscription expiry
- commuter or benefits order updates
- appointment preparation and scheduling
- payment due or payment failure
- payment method update
- application completion
- account verification and retention
- verification code delivery
- security alerts
- site and service issue follow-up
- document signature or availability
- pickup-ready action
- travel check-in

Current strengths:

- the family taxonomy is much broader than the initial skeleton
- it was tuned against a scrubbed mailbox sample

Current limitation:

- active report examples from the earlier smoke batch still show Phase 3 misses for some real messages because those runs were captured before the taxonomy expansion and before further scrubber improvements

Sample artifacts used for tuning:

- [runtime/flow_families/action_required/reports](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/reports)
- [family-mailbox-sample-analysis.md](/home/dan/Projects/HexeEmail/docs/family-mailbox-sample-analysis.md)

## Phase 4 Template Strategy

ACTION_REQUIRED has:

- family-specific template schema ownership
- family-scoped template storage
- unresolved-template AI handoff
- probation storage and reuse

Template roots:

- [runtime/flow_families/action_required/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/templates)
- [runtime/flow_families/action_required/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/templates)

Current template-generation prompt usage:

- the family now participates in the shared multi-family prompt strategy through [prompt.email.family_pattern_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.family_pattern_template_creation.json)
- template generation standardizes deadline extraction on `due_date`; when an ACTION_REQUIRED sample contains an explicit deadline-like date, the generated template should include a `due_date` extractor

Current limitation:

- ACTION_REQUIRED still does not have broad active template coverage
- so the family is structurally ready for AI probation flow, but still light on deterministic active-template coverage

## Probation Flow

ACTION_REQUIRED now follows the same broad probation shape as ORDER.

That includes:

- unresolved-template request mapping
- AI generation handoff
- probation state reuse
- probation evaluation
- promotion framework
- low-confidence probation fallback application

Runtime implementation:

- [src/email_node/flow_families/action_required/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/runtime.py)

Probation paths:

- [runtime/flow_families/action_required/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/templates)
- [runtime/flow_families/action_required/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/state)
- [runtime/flow_families/action_required/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/evaluations)
- [runtime/flow_families/action_required/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/shadow)

## Decisioning

ACTION_REQUIRED uses shared decisioning with family thresholds from `family.yaml`.

Current thresholds:

- high confidence at `0.9`
- medium confidence at `0.65`

That makes ACTION_REQUIRED slightly stricter than ORDER before reaching `accept`.

## Persistence

ACTION_REQUIRED uses shared family-scoped persistence:

- [runtime/flow_families/action_required/outputs](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/outputs)

Persisted trust levels follow the shared model:

- `trusted`
- `partial`
- `review_needed`

## Downstream Actions

ACTION_REQUIRED now has two downstream surfaces:

- family-flow persistence under `runtime/flow_families/action_required/outputs`
- managed Action Required items in the local Gmail action-item database

Configured decision intents:

- `accept` -> `store_action_record`, `user_notification`
- `probation` -> `mark_for_manual_review`
- `review_needed` -> `user_notification`, `mark_for_manual_review`

Configured diagnostic token intents:

- `important_inconsistency` -> `mark_high_priority`, `mark_for_manual_review`
- `deadline` -> `queue_reminder`

Current runtime behavior:

- when mail is classified as `action_required`, `NodeService` runs the family pipeline and action-decision prompt, then syncs or updates a `GmailActionItem`
- the item is grouped by stable action fields such as action URL, document id, account/vendor, or subject fallback
- the item stores source message metadata, extracted fields, flow output, AI decision payload, confidence, priority score, snooze/reminder metadata, review reasons, and operator note
- default queue views hide terminal items and future-snoozed items
- `process_due_action_item_reminders` wakes expired snoozes and sends reminder notifications once
- operator actions can mark state, snooze/remind, add notes, reclassify grouped source messages, resend notification, regenerate the AI decision, and save sender/domain rule feedback

Important nuance:

- the shared action gate blocks `probation` decisions from downstream action execution
- so `probation`-configured intents exist in policy but do not currently pass the gate

## Action Required Item API

Dashboard-friendly API:

- `GET /api/actions`
- `GET /api/actions/{item_id}`
- `PATCH /api/actions/{item_id}/state`
- `PATCH /api/actions/{item_id}/snooze`
- `PATCH /api/actions/{item_id}/note`
- `PATCH /api/actions/{item_id}/classification`
- `POST /api/actions/{item_id}/rule-feedback`
- `POST /api/actions/{item_id}/notify`
- `POST /api/actions/{item_id}/regenerate-ai-decision`
- `POST /api/actions/{item_id}/rerun-processing`

Provider-scoped aliases are available under `/api/gmail/action-items`.

Rule feedback writes enabled sender/domain label overrides into the Gmail runtime rule settings exposed by `/api/gmail/rules`. Non-`action_required` rule feedback marks the current action item ignored because future matching mail should no longer remain in the Action Required queue.

`rerun-processing` keeps the source message's current classification label, reruns the Action Required family flow, forces a fresh AI action decision, and syncs the selected item from the new flow output.

When family extraction has no `due_date`, `deadline`, or `deadline_at`, the item API falls back to parseable AI action-decision deadline mentions for `due_at`.

## Runtime Switch Interaction

Relevant switches:

- `AI Calls`
- `Clasify`
- `Notifications`

Practical effects:

- AI-disabled blocks ACTION_REQUIRED probation template generation
- classification-disabled prevents this family from being reached through the classification-driven pipeline
- notifications-disabled suppresses actual user notification sending at the node notification boundary

## Current Strengths

- broad taxonomy for account and operational action mails
- YAML-backed family config
- AI probation plumbing exists
- consistent shared persistence and review-needed behavior

## Current Gaps

- limited active template coverage
- downstream handlers are still placeholders
- some message types still need scrub robustness improvements

## Related Documents

- [family-template-prompt-strategy.md](/home/dan/Projects/HexeEmail/docs/family-template-prompt-strategy.md)
- [pattern-generation.md](/home/dan/Projects/HexeEmail/docs/pattern-generation.md)
- [shared-flow-family-architecture.md](/home/dan/Projects/HexeEmail/docs/shared-flow-family-architecture.md)
