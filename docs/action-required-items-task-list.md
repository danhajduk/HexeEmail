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

Implementation status:

- Done in `src/providers/gmail/action_item_store.py`.
- Dedicated DB path: `runtime/providers/gmail/action_items.sqlite3`.
- Owned by `GmailProviderAdapter.action_item_store`.

### AR-002: Build item sync from classified mail

- Create or update action items when mail is classified as `action_required`.
- Merge pipeline output from `runtime/flow_families/action_required/outputs`.
- Attach saved `action_decision_payload` from the Gmail message when present.
- Avoid duplicating items for the same thread, action URL, document id, verification target, or sender/profile/deadline group.

Implementation status:

- Done in `NodeService._sync_action_required_item_from_message`.
- Runs from the Action Required classification follow-up path after the family pipeline and AI decision.
- Falls back to persisted family output files when the in-memory pipeline result is not available.
- Groups by action URL, document id, verification target, thread, then sender/profile/deadline.

### AR-003: Add backend Action Required API

- Add list, detail, state update, snooze, note update, and regenerate-AI-decision endpoints.
- Return list-ready summaries and full detail payloads separately.
- Support filters for state, profile, priority, due date, review-needed, sender, and grouped items.

Implementation status:

- Done through `GET /api/actions`, `GET /api/actions/{item_id}`, state/note/snooze patch endpoints, and regenerate-AI-decision.
- Gmail-specific aliases are also available under `/api/gmail/action-items`.
- List responses return summaries; detail responses include extracted fields, flow output, AI decision payload, and source message metadata.

### AR-004: Add priority scoring

- Score by profile, deadline proximity, overdue status, sender reputation, extraction confidence, AI human-review flag, and diagnostics.
- Persist the score and expose the score inputs for operator trust.
- Keep scoring deterministic and locally testable.

Implementation status:

- Done in `NodeService._score_action_item_priority`.
- Score inputs are persisted on `GmailActionItem.priority_inputs` and exposed by the Action Required API.
- Scoring currently includes profile, deadline, confidence, review reasons, AI human-review flag, sender reputation, and diagnostics.

### AR-005: Add snooze and reminder handling

- Store `snoozed_until` and `reminder_at`.
- Hide snoozed items from the default active list until they wake.
- Add a scheduled reminder check that sends user notifications for due reminders.
- Prevent repeated reminder spam with reminder delivery timestamps.

Implementation status:

- Done through the Action Required snooze API plus `process_due_action_item_reminders`.
- Future-snoozed items are hidden from the default Action Required list unless explicitly filtering for `snoozed`.
- Added the `action_required_reminders` scheduled task on the five-minute cadence.
- Reminder delivery sets `reminder_sent_at` so a reminder is not sent repeatedly.

### AR-006: Add review queue rules

- Mark items `review_needed` when extraction confidence is low, required fields are missing, AI requests human review, profiles conflict, or no clear action URL/details exist.
- Provide a dashboard filter for review queue.
- Preserve the reason codes in the item detail.

Implementation status:

- Done in `NodeService._action_required_review_reasons`.
- Items move to `review_needed` for low/missing confidence, missing profile, missing action details, missing/invalid required fields, review/failure/conflict diagnostics, or AI human-review requests.
- Review reason codes are persisted on each action item and exposed through the Action Required API.

### AR-007: Add `#/dashboard/actions` page and navigation

- Add a dashboard nav entry for Action Required.
- Add the dashboard route and page wrapper.
- Keep the first screen as the usable Action Required workspace, not a landing page.

Implementation status:

- Done through the `actions` dashboard route, sidebar entry, and `ActionRequiredSection` workspace.

### AR-008: Build Action Required list table

- Show sender.
- Show subject.
- Show received date.
- Show profile/type, such as `payment_due`, `document_signature_required`, or `pickup_ready_action_required`.
- Show current state.
- Show urgency/deadline when extracted.
- Show confidence as a pill.
- Show AI decision summary.
- Show grouped/thread count when present.
- Include filters for active, review needed, snoozed, done, ignored, high priority, and profile.

Implementation status:

- Done with an Action Required table backed by `GET /api/actions`, including state, priority, sender, subject, profile, due/reminder, confidence, review reasons, AI summary, grouped thread count, and local filters.

### AR-009: Build mail review panel

- Show subject, sender, recipients, and date.
- Show plain text body.
- Show sanitized HTML preview.
- Show Gmail labels.
- Link to the original Gmail message if a stable Gmail URL can be built.

Implementation status:

- Done in the selected item detail view using source-message metadata, stored text, sandboxed sanitized HTML preview, Gmail labels, and a Gmail message link.

### AR-010: Build extracted data panel

- Show flow-family output.
- Show profile detected.
- Show extracted fields such as action URL, due date, verification code, amount, account/vendor, and document ID.
- Show template used.
- Show extraction confidence and diagnostics.
- Show review-needed reason codes.

Implementation status:

- Done in the selected item detail view with profile, template, action URL, due date, confidence, review reasons, extracted fields, diagnostics, and collapsible flow-output JSON.

### AR-011: Build AI decision panel

- Show primary label.
- Show recommended action.
- Show whether human review is required.
- Show risk notes.
- Show deadline and calendar signals.
- Show raw parsed JSON behind a debug disclosure.

Implementation status:

- Done in the selected item detail view with primary label, recommendation, human-review state, risk notes, deadline/calendar signals, recommended action list, and collapsible raw AI JSON.

### AR-012: Add operator actions

- Mark done.
- Snooze or set reminder.
- Ignore.
- Mark needs review.
- Reclassify label.
- Open action URL.
- Add note.
- Regenerate AI decision.
- Send notification again.

Implementation status:

- Done with operator controls in the Action Required detail view and API support for state changes, snooze/reminder, notes, reclassification, notification resend, AI-decision regeneration, and opening the extracted action URL.
- Reclassification updates grouped source messages as manual classifications; non-`action_required` reclassification moves the item to `ignored`.

### AR-013: Add rule feedback from item detail

- Allow operator actions such as always action-required for this sender/domain or never action-required for this sender/domain.
- Write through to the Gmail sender rule settings.
- Record feedback on the action item audit trail.

Implementation status:

- Done with `POST /api/actions/{item_id}/rule-feedback` and the matching Gmail action-item alias.
- The endpoint writes enabled sender/domain label override rules into Gmail runtime rule settings and records a timestamped rule-feedback line in the item operator note.
- The dashboard detail view includes generic sender/domain rule saves plus quick always/never sender/domain controls.

### AR-014: Add action item tests and docs

- Cover store behavior, item grouping, state transitions, snooze/reminder behavior, priority scoring, API contracts, and dashboard rendering.
- Update dashboard, API, and action-required family docs with the final behavior.

Implementation status:

- Done with targeted backend coverage for the store, sync/grouping, priority/review state, snooze/reminder behavior, API mutations, grouped reclassification, notification resend, AI-decision regeneration, and sender/domain rule feedback.
- Done with dashboard rendering coverage for the Action Required queue, detail panels, operator controls, and rule feedback controls.
- Updated the API map, dashboard UI reference, and ACTION_REQUIRED family reference to describe the final item workspace behavior.

## MVP Build Order

1. Data store and sync from classified messages.
2. Backend list/detail/state/snooze APIs.
3. Dashboard page, list table, and detail panels.
4. Operator actions.
5. Priority scoring and review queue filters.
6. Reminder scheduler and user notification.
7. Rule feedback integration.
