# ORDER Phase 2 Transactional Targeting

Phase 2 now performs transactional-content targeting before final line normalization.

Current targeting behavior:

- score candidate content blocks from the selected-body extraction path and the Phase 1 text fallback using order-first weights
- prefer blocks with order anchors such as `Thanks for your order`, `Order #`, `Quantity`, `Grand Total`, and delivery-status markers
- rank candidates by their expanded neighborhood score, not just the seed block score
- merge nearby complementary blocks for split order content such as status, order id, action link, item, quantity, and totals
- recover nearby greeting context when a strong order block is found without the greeting line
- reject promo-heavy merge candidates and record the rejection in diagnostics
- suppress recommendation and promo fragments before final semantic line compaction
- prioritize order-action and tracking-action links ahead of generic promo/product links
- sanitize malformed order-action URLs before validation and repair recoverable `orderID` values from nearby visible context
- mark scrub quality as partial or failed when core transactional fields are missing

The updater for the current ORDER mail list now lives in [scripts/update_order_flow_tests.py](/home/dan/Projects/HexeEmail/scripts/update_order_flow_tests.py) and refreshes:

- per-message logs in [runtime/order_flow_logs](/home/dan/Projects/HexeEmail/runtime/order_flow_logs)
- the shared markdown report in [docs/order_flow_tests.md](/home/dan/Projects/HexeEmail/docs/order_flow_tests.md)

It preserves existing `Phase 1 output:` blocks and replaces only `Phase 2 output:` blocks when entries already exist.
