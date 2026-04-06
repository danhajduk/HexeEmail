# Planned Family References

This document describes the current intended behavior of the newer shared-core flow families:

- `financial`
- `invoice`
- `security`
- `shipment`

These families already have:

- shared-core runtime wiring
- family YAML
- first-pass taxonomy and decision policy
- family-scoped output and report paths
- smoke-test coverage

They do not yet have broad active template coverage or final downstream integrations.

## FINANCIAL

Primary files:

- [src/email_node/pipeline/financial_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/financial_flow.py)
- [src/email_node/flow_families/financial/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/runtime.py)
- [runtime/flow_families/financial/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/family.yaml)

Intended taxonomy:

- `statement_ready`
- `payment_due`
- `payment_received`
- `refund_processed`
- `balance_alert`
- `tax_document_ready`
- `generic_financial_update`

Expected detection patterns:

- statement-ready language
- amount-due and due-date language
- payment-posted and refund-issued language
- balance alerts
- tax form readiness

Current action surface:

- `store_financial_record`
- `user_notification`
- `mark_for_manual_review`

Current handler maturity:

- placeholder queue results only

Mailbox sample artifacts:

- [financial_mailbox_sample.json](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/analysis/financial_mailbox_sample.json)
- [financial_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/analysis/financial_mailbox_sample.md)

## INVOICE

Primary files:

- [src/email_node/pipeline/invoice_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/invoice_flow.py)
- [src/email_node/flow_families/invoice/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/runtime.py)
- [runtime/flow_families/invoice/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/family.yaml)

Intended taxonomy:

- `invoice_ready`
- `invoice_due`
- `receipt_issued`
- `payment_confirmed`
- `overdue_billing_notice`
- `generic_invoice_update`

Expected detection patterns:

- invoice availability
- invoice payment requested
- receipt or billing statement issuance
- payment confirmed
- overdue or late payment notices

Special behavior:

- Phase 3 can override shared scrub failure when usable text still exists

Current action surface:

- `store_invoice_record`
- `user_notification`
- `mark_for_manual_review`

Current handler maturity:

- placeholder queue results only

Mailbox sample artifacts:

- [invoice_mailbox_sample.json](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/analysis/invoice_mailbox_sample.json)
- [invoice_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/analysis/invoice_mailbox_sample.md)

## SECURITY

Primary files:

- [src/email_node/pipeline/security_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/security_flow.py)
- [src/email_node/flow_families/security/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/security/runtime.py)
- [runtime/flow_families/security/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/security/family.yaml)

Intended taxonomy:

- `security_alert`
- `suspicious_login`
- `password_reset`
- `identity_verification`
- `mfa_code`
- `new_device_login`
- `generic_security_notice`

Expected detection patterns:

- suspicious sign-in and unusual activity
- password reset or password change
- verify identity or account security confirmation
- MFA and verification code delivery
- new device or new browser login alerts

Special behavior:

- Phase 3 can override shared scrub failure when usable text still exists

Current action surface:

- `store_security_record`
- `user_notification`
- `mark_for_manual_review`

Current handler maturity:

- placeholder queue results only

Mailbox sample artifacts:

- [security_mailbox_sample.json](/home/dan/Projects/HexeEmail/runtime/flow_families/security/analysis/security_mailbox_sample.json)
- [security_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/security/analysis/security_mailbox_sample.md)

## SHIPMENT

Primary files:

- [src/email_node/pipeline/shipment_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/shipment_flow.py)
- [src/email_node/flow_families/shipment/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/shipment/runtime.py)
- [runtime/flow_families/shipment/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/shipment/family.yaml)

Intended taxonomy:

- `shipped`
- `out_for_delivery`
- `delivered`
- `delayed`
- `label_created`
- `generic_shipment_update`

Expected detection patterns:

- shipped and on-the-way language
- delivery-today and out-for-delivery language
- delivered confirmations
- delay or transit-exception notices
- label-created or awaiting-carrier-pickup notices

Current action surface:

- `store_shipment_record`
- `user_notification`
- `mark_for_manual_review`

Current handler maturity:

- placeholder queue results only

Mailbox sample artifacts:

- [shipment_mailbox_sample.json](/home/dan/Projects/HexeEmail/runtime/flow_families/shipment/analysis/shipment_mailbox_sample.json)
- [shipment_mailbox_sample.md](/home/dan/Projects/HexeEmail/runtime/flow_families/shipment/analysis/shipment_mailbox_sample.md)

## Shared Limitations Across These Families

All four families currently share the same big gaps:

- limited or no active template inventory
- no family-owned real downstream side effects yet
- placeholder queue results instead of final persistence integrations
- taxonomy is first-pass and still expected to evolve with more mailbox sampling and template work
