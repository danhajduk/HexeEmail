# ORDER Phase 2 Scrubber

The ORDER Phase 2 scrubber now lives in [src/providers/gmail/order_phase2.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase2.py).

Current Phase 2 responsibilities:

- accept only Phase 1 payloads marked `handoff_ready`
- preserve a compact Phase 1 reference block without letting raw Phase 1 bodies become canonical Phase 2 content
- create a Phase 2 working object for scrubber operations
- extract visible text from HTML while skipping hidden content, head/script/style markup, and tracking pixels
- normalize plain text bodies into a stable parser-friendly representation
- target the most complete transactional region by scoring expanded block neighborhoods instead of isolated blocks
- remove generic email chrome, footer/legal blocks, and seller-agnostic junk lines
- preserve status, greeting, and order-identifier lines as top-priority semantic output when present
- normalize semantic lines and produce a compact scrubbed text field
- extract important links into a structured inventory separate from scrubbed text
- sanitize and repair recoverable order-action URLs while keeping raw link input for diagnostics
- record deterministic stage statuses, diagnostics, applied rules, and lightweight reduction metrics
- expose canonical Phase 2 fields through `scrubbed_text`, `normalized_lines`, `extracted_links`, `scrub_metrics`, `applied_rules`, `scrub_status`, and `scrub_diagnostics`

Supporting modules:

- [src/providers/gmail/order_html_extractor.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_html_extractor.py)
- [src/providers/gmail/order_scrubber_rules.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_scrubber_rules.py)

Phase 2 tests live in [tests/test_gmail_order_phase2.py](/home/dan/Projects/HexeEmail/tests/test_gmail_order_phase2.py).
