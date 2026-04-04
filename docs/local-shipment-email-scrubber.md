# Local Shipment Email Scrubber

The Gmail local shipment email scrubber is a deterministic, local-only reconciler that updates existing shipment records from supported seller and carrier emails.

Scope:
- no AI or external model calls
- lightweight regex and exact-match rules only
- existing-order-only processing
- explicit supported domains only

Current supported sender domains:
- `amazon.com`
- `doordash.com`
- `fedex.com`
- `ups.com`
- `usps.com`
- `dhl.com`

Boundary rules:
- seller mail is only checked against that seller's existing orders
- carrier mail is only checked when the existing record is already linked to that carrier or tracking number
- unsupported domains are skipped
- if no existing shipment record exists, the scrubber skips processing
- the scrubber does not create new shipment records from incoming email

Matching priority:
1. exact normalized `tracking_number`
2. exact normalized `order_number + domain`
3. exact normalized `order_number + seller`

Status extraction is intentionally simple and currently recognizes:
- `out for delivery`
- `delivered`
- `arriving overnight`
- `arriving today`
- `arriving tomorrow`
- `in transit`
- `shipped`

This flow is intended as a low-cost enrichment pass for already-known orders, not as a general shipment parser or email classifier.
