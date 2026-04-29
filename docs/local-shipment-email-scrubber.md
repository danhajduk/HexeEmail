# Local Shipment Email Scrubber

The Gmail local shipment email scrubber is a deterministic, local-only reconciler that updates shipment records from supported seller and carrier emails.

Scope:
- no AI or external model calls
- lightweight regex and exact-match rules only
- existing-order processing for seller mail
- standalone shipment creation for supported carrier mail with a tracking number or status signal
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
- carrier mail first updates an existing linked record when the tracking number matches
- carrier mail creates a standalone shipment record when no linked order exists but the message has a tracking number or status signal
- unsupported domains are skipped

Matching priority:
1. exact normalized `tracking_number`
2. exact normalized `order_number + domain`
3. exact normalized `order_number + seller`

Status extraction is intentionally simple and currently recognizes:
- `out for delivery`
- `delivered`
- `on the way`
- `scheduled delivery`
- `label created`
- `arriving overnight`
- `arriving today`
- `arriving tomorrow`
- `in transit`
- `shipped`

This flow is intended as a low-cost enrichment pass for known orders and standalone carrier shipment notices, not as a general shipment parser or email classifier.
