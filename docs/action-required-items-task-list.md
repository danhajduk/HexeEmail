# Action Required Items Task List

This task list defines the planned Action Required item workspace for `#/dashboard/actions`.

## Suggested Item States

Canonical stored states:

- `new`: created from a classified `action_required` message and not reviewed yet
- `review_needed`: extraction, profile, or AI decision needs operator review
- `ready`: enough data exists for the operator to act
- `snoozed`: hidden until a reminder time
- `waiting`: action was started, but completion depends on an outside response
- `done`: operator completed or resolved the action
- `ignored`: operator dismissed the item as not actionable

Computed badges:

- `due_soon`: due within the configured warning window
- `overdue`: due date is in the past and item is not terminal
- `high_priority`: priority score crosses the high threshold or diagnostics mark urgency
- `grouped`: item is part of a sender/thread/action-url group

Terminal states:

- `done`
- `ignored`

## Suggested Profiles And Types

Payment and billing:

- `payment_due`
- `payment_method_update_required`
- `subscription_payment_failed`

Account and security:

- `account_verification_required`
- `verification_code_required`
- `security_alert_action_required`
- `account_retention_required`

Documents:

- `document_signature_required`
- `document_available_action_required`

Appointments and travel:

- `appointment_preparation_required`
- `appointment_scheduling_required`
- `travel_check_in_required`

Benefits and subscriptions:

- `subscription_expiring`
- `benefit_order_update_required`
- `benefit_expiring`

Service follow-up:

- `site_issue_action_required`
- `service_issue_action_required`

Pickup and general:

- `pickup_ready_action_required`
- `application_completion_required`
- `generic_action_required`

## Implementation Tasks

### AR-001: Add Action Required item data store

- Create a dedicated local SQLite store for action items.
- Store one item per actionable group, not necessarily one item per email.
- Persist source Gmail message id, thread id, sender, subject, received time, state, profile, extracted fields, AI decision payload, confidence, priority score, snooze/reminder fields, operator notes, grouped message ids, and audit timestamps.
- Keep Gmail message classification as source evidence, not the managed item state.

### AR-002: Build item sync from classified mail

- Create or update action items when mail is classified as `action_required`.
- Merge pipeline output from `runtime/flow_families/action_required/outputs`.
- Attach saved `action_decision_payload` from the Gmail message when present.
- Avoid duplicating items for the same thread, action URL, document id, verification target, or sender/profile/deadline group.

### AR-003: Add backend Action Required API

- Add list, detail, state update, snooze, note update, and regenerate-AI-decision endpoints.
- Return list-ready summaries and full detail payloads separately.
- Support filters for state, profile, priority, due date, review-needed, sender, and grouped items.

### AR-004: Add priority scoring

- Score by profile, deadline proximity, overdue status, sender reputation, extraction confidence, AI human-review flag, and diagnostics.
- Persist the score and expose the score inputs for operator trust.
- Keep scoring deterministic and locally testable.

### AR-005: Add snooze and reminder handling

- Store `snoozed_until` and `reminder_at`.
- Hide snoozed items from the default active list until they wake.
- Add a scheduled reminder check that sends user notifications for due reminders.
- Prevent repeated reminder spam with reminder delivery timestamps.

### AR-006: Add review queue rules

- Mark items `review_needed` when extraction confidence is low, required fields are missing, AI requests human review, profiles conflict, or no clear action URL/details exist.
- Provide a dashboard filter for review queue.
- Preserve the reason codes in the item detail.

### AR-007: Build `#/dashboard/actions` list UI

- Add a dashboard nav entry for Action Required.
- Show sender, subject, profile, state, priority, due/reminder time, confidence, grouped count, and AI decision summary.
- Include filters for active, review needed, snoozed, done, ignored, high priority, and profile.

### AR-008: Build Action Required detail UI

- Show mail review with headers, plain text, and sanitized HTML preview.
- Show extracted data from the family pipeline.
- Show AI decision summary and raw JSON in a debug disclosure.
- Show grouped emails and source evidence.
- Provide operator actions: mark done, ignore, needs review, ready, waiting, snooze, add note, regenerate AI decision, and open action URL.

### AR-009: Add rule feedback from item detail

- Allow operator actions such as always action-required for this sender/domain or never action-required for this sender/domain.
- Write through to the Gmail sender rule settings.
- Record feedback on the action item audit trail.

### AR-010: Add action item tests and docs

- Cover store behavior, item grouping, state transitions, snooze/reminder behavior, priority scoring, API contracts, and dashboard rendering.
- Update dashboard, API, and action-required family docs with the final behavior.

## MVP Build Order

1. Data store and sync from classified messages.
2. Backend list/detail/state/snooze APIs.
3. Dashboard list and detail view.
4. Priority scoring and review queue filters.
5. Reminder scheduler and user notification.
6. Rule feedback integration.
