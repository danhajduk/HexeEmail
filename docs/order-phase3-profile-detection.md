# ORDER Phase 3 Profile Detection

The ORDER Phase 3 detector lives in [src/providers/gmail/order_phase3.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase3.py).

Current Phase 3 responsibilities:

- accept only Phase 2 payloads with usable scrubbed output
- preserve the full Phase 2 payload unchanged as the Phase 3 reference object
- separate sender identity from resolved profile identity
- generate deterministic profile candidates from sender, subject, scrubbed text, and normalized lines
- score and rank profile candidates with inspectable deterministic rules
- resolve one canonical `profile_id` plus fallback candidates for downstream pattern lookup
- downgrade confidence when strong signals conflict or the leading candidate is weak

The initial taxonomy and known vendor mappings live in [src/providers/gmail/order_profile_taxonomy.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_profile_taxonomy.py).

The runtime-tunable keyword and scoring rules now live in [runtime/order_profile_rules.json](/home/dan/Projects/HexeEmail/runtime/order_profile_rules.json). This file controls Phase 3 signal keywords, score weights, thresholds, sender-domain profile hints, and conflict overrides without requiring code edits.

Current sample-grounded profile coverage includes:

- Amazon order confirmation and status shapes
- Dutchie pickup-ready notifications
- Walmart curbside pickup messages
- Recreation.gov reservation confirmations
- Edenred upcoming-order notices
- generic order confirmation, status-update, and cancellation fallbacks
