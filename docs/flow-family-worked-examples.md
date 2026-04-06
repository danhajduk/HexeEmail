# Flow-Family Worked Examples

This document walks through representative real or repo-backed examples across the current families.

## Example 1: Amazon ORDER Confirmation

Message source:

- [order_flow_report.current.index.json](/home/dan/Projects/HexeEmail/runtime/order_flow_logs/ad_hoc_reports/order_flow_report.current.index.json)
- message id `19d56c0462707ad1`

Observed flow:

1. Phase 2 scrub succeeds on a known transactional order message.
2. Phase 3 resolves `amazon_order_confirmation` at `0.85` confidence.
3. Phase 4 matches active template `amazon_order_confirmation.v1` and succeeds.
4. Phase 6 decides `accept`.
5. Phase 7 persists the structured result as `trusted`.
6. ORDER downstream actions are eligible.

Why it matters:

- this is the current gold path for a mature family

## Example 2: Recreation.gov Reservation ORDER Mail

Message source:

- [order_flow_report.current.index.json](/home/dan/Projects/HexeEmail/runtime/order_flow_logs/ad_hoc_reports/order_flow_report.current.index.json)
- message id `19d3f37023f5375e`

Observed flow:

1. Phase 3 resolves `reservation_confirmation` at `0.65` confidence.
2. Phase 4 does not have a fully trusted active path, but a probation template exists.
3. Probation template `recreation_gov_reservation_confirmation.v1` is reused.
4. Phase 4 becomes `partial`.
5. Phase 6 decides `probation`.
6. Phase 7 persists the result as `partial`.
7. Downstream actions are blocked because the decision is probation.

Why it matters:

- it shows the live low-confidence fallback path without losing the extracted structure

## Example 3: Unknown ORDER Mail That Fell Back To Generated Probation

Message source:

- [order_flow_report.current.index.json](/home/dan/Projects/HexeEmail/runtime/order_flow_logs/ad_hoc_reports/order_flow_report.current.index.json)
- message id `19d3170a96347d98`

Observed flow:

1. Phase 3 has no resolved profile.
2. Phase 4 still reaches a probation-generated template path.
3. The generated template `meowwolf_generic_order_confirmation.v1` is applied.
4. Phase 4 becomes `partial`.
5. Phase 6 decides `probation`.
6. Phase 7 persists as `partial`.

Why it matters:

- it demonstrates that unknown ORDER mails no longer have to fail closed when the family can synthesize a probation template

## Example 4: Ride-Cancellation ORDER Mail

Message source:

- [order_flow_report.current.index.json](/home/dan/Projects/HexeEmail/runtime/order_flow_logs/ad_hoc_reports/order_flow_report.current.index.json)
- message id `19d360a5ed27d93c`

Observed flow:

1. Phase 3 resolves `ride_cancellation` at `0.85` after the ride-specific taxonomy tuning.
2. Phase 4 uses probation template `notifications_ride_cancellation.v1`.
3. Phase 6 decides `probation`.
4. Phase 7 persists as `partial`.

Why it matters:

- it shows the benefit of contextual Phase 3 tuning
- the old generic cancellation downgrade path no longer misreads ride pickup/drop-off terms

## Example 5: ACTION_REQUIRED Mail With Current Gaps

Message source:

- [action_required_flow_report.renamecheck.index.json](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/reports/action_required_flow_report.renamecheck.index.json)
- example message id `19d4c495c9838b45`

Observed flow in the captured smoke batch:

1. Phase 3 does not resolve a profile.
2. Phase 4 fails because there is no profile/template context.
3. Phase 6 decides `reject` in that historical batch.
4. Phase 7 does not persist a structured output.

Why it matters:

- it shows where ACTION_REQUIRED still needs active template coverage and more runtime seasoning
- it is also a reminder that some stored reports predate the later review-needed and taxonomy improvements

Current architecture note:

- the family now has AI probation plumbing and broader taxonomy than this report alone suggests

## Example 6: Planned-Family Smoke Path

Representative source material:

- [financial_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/analysis/financial_mailbox_sample.md)
- [invoice_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/analysis/invoice_mailbox_sample.md)
- [security_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/security/analysis/security_mailbox_sample.md)
- [shipment_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/shipment/analysis/shipment_mailbox_sample.md)

Expected current path for these families:

1. Phase 2 scrubs the message with family heuristics.
2. Phase 3 may resolve a first-pass taxonomy profile.
3. Phase 4 usually lacks broad active template coverage today.
4. The flow therefore tends toward `review_needed` or family-local placeholder behavior until template coverage grows.
5. Phase 7 can still persist review-oriented outputs because of the shared outcome model.

Why it matters:

- these families are structurally integrated, but not yet as production-complete as ORDER
