# ORDER Phase 4 Template Extraction

The ORDER Phase 4 extractor lives in [src/providers/gmail/order_phase4.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase4.py) and resolves deterministic JSON templates from [src/providers/gmail/order_template_registry.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_template_registry.py).

Current Phase 4 responsibilities:

- accept only Phase 3 payloads with a resolved `profile_id` and usable scrubbed text
- preserve the full Phase 3 payload as the reference object for downstream review
- resolve one active template plus fallback candidates by `profile_id` and optional vendor identity
- run only built-in deterministic extraction methods such as `regex`, `line_after`, `between_markers`, and link lookups
- normalize extracted values through controlled built-in transforms instead of arbitrary code
- validate required fields, record field-level diagnostics, and compute extraction confidence
- emit unresolved results with an `ai_template_hook` package when no template exists

The initial template set lives in [runtime/order_templates](/home/dan/Projects/HexeEmail/runtime/order_templates) and currently covers:

- `amazon_order_confirmation`
- `pickup_ready_notification`
- `generic_order_confirmation`
- `generic_order_status_update`

The current ORDER sample updater in [scripts/update_order_flow_tests.py](/home/dan/Projects/HexeEmail/scripts/update_order_flow_tests.py) now preserves existing `Phase 1 output:`, `Phase 2 output:`, and `Phase 3 output:` blocks while replacing only `Phase 4 output:` blocks in:

- [docs/order_flow_tests.md](/home/dan/Projects/HexeEmail/docs/order_flow_tests.md)
- [runtime/order_flow_logs](/home/dan/Projects/HexeEmail/runtime/order_flow_logs)
