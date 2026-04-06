# ORDER Phase 3 Profile Detection

The ORDER Phase 3 detector lives in [src/providers/gmail/order_phase3.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase3.py).
Its shared detection mechanics now come from [src/email_node/shared_pipeline_core/profile_detector.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/profile_detector.py).

Current Phase 3 responsibilities:

- accept only Phase 2 payloads with usable scrubbed output
- preserve the full Phase 2 payload unchanged as the Phase 3 reference object
- separate sender identity from resolved profile identity
- generate deterministic profile candidates from sender, subject, scrubbed text, and normalized lines
- score and rank profile candidates with inspectable deterministic rules
- resolve one canonical `profile_id` plus fallback candidates for downstream pattern lookup
- downgrade confidence when strong signals conflict or the leading candidate is weak

The ORDER family taxonomy and known vendor mappings now live in [src/email_node/flow_families/order/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/profiles.py).

The default ORDER keyword and scoring rules also live in [src/email_node/flow_families/order/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/profiles.py), while runtime overrides still live in [runtime/order_profile_rules.json](/home/dan/Projects/HexeEmail/runtime/order_profile_rules.json). That runtime file controls Phase 3 signal keywords, score weights, thresholds, sender-domain profile hints, and conflict overrides without requiring code edits.

Current sample-grounded profile coverage includes:

- Amazon order confirmation and status shapes
- Dutchie pickup-ready notifications
- Walmart curbside pickup messages
- Recreation.gov reservation confirmations
- Edenred upcoming-order notices
- ride receipts and ride cancellations
- generic order confirmation, status-update, and cancellation fallbacks

The runtime rules file is organized into:

- `signals`: keyword lists used to generate and score candidates
- `sender_domain_profiles`: deterministic sender-domain to profile hints
- `weights`: integer score adjustments for candidate ranking
- `thresholds`: confidence score cutoffs and clamp values
- `conflicts`: downgrade pairs and ignore overrides
