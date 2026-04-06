# Shared Email Pipeline Core

The shared email pipeline core is the first migration seam for multi-flow processing.

Current scope:

- shared Phase 1 normalization interface
- shared orchestration for Phase 2 through Phase 7
- shared Phase 2 scrub engine with loaded heuristic packs
- shared Phase 3 profile detector engine with external taxonomy and rules inputs
- shared Phase 4 template registry and execution engine
- shared probation lifecycle core for evaluation, metrics, promotion, and shadow comparison
- shared Phase 5 validation and confidence policy framework
- shared Phase 6 decision framework
- shared Phase 7 persistence and action-gating framework
- shared diagnostics and report builder
- flow-family identity carried with the pipeline result
- family config loaded from one shared entry point
- YAML-backed declarative family config with Python fallback-compatible loaders
- flow-specific logic remains injected as hooks

Shared terminal decisions now available through the common Phase 6 contract:

- `accept`: trusted active-template result, persisted and action-eligible
- `probation`: low-trust result, persisted as partial and blocked from downstream actions
- `review_needed`: family flow could not complete safely, but the result should still be persisted and surfaced for operator or user review
- `reject`: hard stop with no persisted structured result

Current flow families:

- `order`
- `action_required`
- `financial`
- `invoice`
- `security`
- `shipment`

Shared family entry point:

- [src/email_node/shared_pipeline_core/families.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/families.py)

Current family config responsibilities:

- scrub heuristic pack reference
- profile detector pack reference
- template directory
- probation template directory
- probation state directory
- family-scoped runtime storage layout
- validation policy reference
- decision policy reference
- action router policy reference
- output schema family
- family-owned report and output paths

Current declarative family config:

- ORDER: [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)
- ACTION_REQUIRED: [runtime/flow_families/action_required/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/family.yaml)
- FINANCIAL: [runtime/flow_families/financial/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/family.yaml)
- INVOICE: [runtime/flow_families/invoice/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/family.yaml)
- SECURITY: [runtime/flow_families/security/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/security/family.yaml)
- SHIPMENT: [runtime/flow_families/shipment/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/shipment/family.yaml)

Schema:

- [flow-family-config.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/flow-family-config.schema.json)

Current family wrapper modules:

- ORDER:
  - [src/email_node/flow_families/order/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/heuristics.py)
  - [src/email_node/flow_families/order/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/profiles.py)
  - [src/email_node/flow_families/order/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/validation.py)
  - [src/email_node/flow_families/order/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/decision.py)
- ACTION_REQUIRED:
  - [src/email_node/flow_families/action_required/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/heuristics.py)
  - [src/email_node/flow_families/action_required/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/profiles.py)
  - [src/email_node/flow_families/action_required/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/validation.py)
  - [src/email_node/flow_families/action_required/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/decision.py)
- FINANCIAL:
  - [src/email_node/flow_families/financial/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/heuristics.py)
  - [src/email_node/flow_families/financial/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/profiles.py)
  - [src/email_node/flow_families/financial/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/validation.py)
  - [src/email_node/flow_families/financial/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/decision.py)
- INVOICE:
  - [src/email_node/flow_families/invoice/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/heuristics.py)
  - [src/email_node/flow_families/invoice/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/profiles.py)
  - [src/email_node/flow_families/invoice/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/validation.py)
  - [src/email_node/flow_families/invoice/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/decision.py)
- SECURITY:
  - [src/email_node/flow_families/security/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/security/heuristics.py)
  - [src/email_node/flow_families/security/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/security/profiles.py)
  - [src/email_node/flow_families/security/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/security/validation.py)
  - [src/email_node/flow_families/security/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/security/decision.py)
- SHIPMENT:
  - [src/email_node/flow_families/shipment/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/shipment/heuristics.py)
  - [src/email_node/flow_families/shipment/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/shipment/profiles.py)
  - [src/email_node/flow_families/shipment/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/shipment/validation.py)
  - [src/email_node/flow_families/shipment/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/shipment/decision.py)

Those modules are now thin YAML-backed adapters rather than the source of truth for declarative family data.

Current ORDER integration:

- [src/service.py](/home/dan/Projects/HexeEmail/src/service.py) now calls Phase 1 through [src/email_node/shared_pipeline_core/phase1.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/phase1.py)
- [src/email_node/pipeline/order_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_flow.py) now delegates phase orchestration to [src/email_node/shared_pipeline_core/pipeline.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/pipeline.py)
- [src/providers/gmail/order_phase2.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase2.py) now uses [src/email_node/shared_pipeline_core/scrub_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/scrub_engine.py) with the ORDER heuristic pack from [src/providers/gmail/order_scrubber_rules.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_scrubber_rules.py)
- [src/providers/gmail/order_phase3.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase3.py) now delegates profile detection mechanics to [src/email_node/shared_pipeline_core/profile_detector.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/profile_detector.py) while continuing to supply ORDER-specific taxonomy and rules
- [src/providers/gmail/order_template_registry.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_template_registry.py) now delegates template loading, lookup, and schema validation to [src/email_node/shared_pipeline_core/template_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/template_engine.py)
- [src/providers/gmail/order_phase4.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_phase4.py) now delegates template execution, field validation, and confidence scoring to [src/email_node/shared_pipeline_core/template_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/template_engine.py) while keeping ORDER-specific AI fallback hook behavior
- [src/email_node/shared_pipeline_core/template_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/template_engine.py) now delegates required-field checks, field-format validation, and confidence scoring to [src/email_node/shared_pipeline_core/validation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/validation.py)
- [src/email_node/pipeline/order_decision_engine.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_decision_engine.py) now thinly wraps the shared decision framework in [src/email_node/shared_pipeline_core/decision.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/decision.py)
- the ORDER decision wrapper now loads its thresholds from [src/email_node/flow_families/order/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/decision.py)
- [src/email_node/pipeline/order_output_handler.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_output_handler.py) now thinly wraps the shared persistence gate in [src/email_node/shared_pipeline_core/persistence.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/persistence.py), while preserving the current ORDER output record shape and legacy `runtime/order_outputs` layout
- [src/email_node/pipeline/order_action_gate.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_action_gate.py) now thinly wraps the shared action authorization logic in [src/email_node/shared_pipeline_core/actions.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/actions.py)
- [src/email_node/pipeline/order_action_router.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_action_router.py) now thinly wraps the shared policy-driven action router in [src/email_node/shared_pipeline_core/actions.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/actions.py), and loads ORDER action intents from [src/email_node/flow_families/order/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/action_routing.py)
- ACTION_REQUIRED now has its own placeholder action policy pack in [src/email_node/flow_families/action_required/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/action_routing.py)
- [scripts/run_order_flow_ad_hoc.py](/home/dan/Projects/HexeEmail/scripts/run_order_flow_ad_hoc.py) now builds JSON and Markdown reports through [src/email_node/shared_pipeline_core/reporting.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/reporting.py), which adds a shared report summary block and explicit `flow_family`
- [src/email_node/pipeline/order_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_flow.py) is now a thin ORDER runner that delegates the actual family wiring and probation behavior to [src/email_node/flow_families/order/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/runtime.py)
- unresolved or hard-validation ORDER results now map to `review_needed` instead of being dropped as plain rejects, so they can persist under the review-needed bucket and queue manual-review-facing intents

Current ACTION_REQUIRED integration:

- [src/email_node/pipeline/action_required_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/action_required_flow.py) now provides an initial thin shared-core runner for the `action_required` family
- [src/email_node/flow_families/action_required/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/runtime.py) wires the shared scrub, profile-detection, template, probation, decision, persistence, and action-gating layers together with placeholder downstream action handlers
- the ACTION_REQUIRED family now has unresolved-template AI handoff, probation-state reuse, and low-confidence probation fallback behavior, but it still does not have active template coverage or family-owned downstream actions
- unresolved ACTION_REQUIRED results now also use the shared `review_needed` decision so they can persist and surface manual-review signals consistently with ORDER
- [src/email_node/patterns/probation_evaluator.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_evaluator.py), [src/email_node/patterns/probation_metrics.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_metrics.py), [src/email_node/patterns/probation_policy.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_policy.py), and [src/email_node/patterns/probation_promotion.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_promotion.py) now thinly wrap the shared probation subsystem in [src/email_node/shared_pipeline_core/probation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/probation.py)
- ORDER still owns its current route-selection policy and downstream action handlers

Current FINANCIAL integration:

- [src/email_node/pipeline/financial_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/financial_flow.py) now provides the initial thin shared-core runner for the `financial` family
- [src/email_node/flow_families/financial/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/runtime.py) wires the shared scrub, profile-detection, template, decision, persistence, and action-gating layers together with placeholder family handlers
- the FINANCIAL family now has a first-pass YAML taxonomy for statement-ready, payment-due, payment-received, refund, balance-alert, tax-document, and generic financial update signals
- FINANCIAL still needs mailbox-sampled refinement and active template coverage, but it now resolves real Phase 3 profiles instead of only failing closed

Current INVOICE integration:

- [src/email_node/pipeline/invoice_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/invoice_flow.py) now provides the initial thin shared-core runner for the `invoice` family
- [src/email_node/flow_families/invoice/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/runtime.py) wires the shared scrub, profile-detection, template, decision, persistence, and action-gating layers together with placeholder family handlers
- the INVOICE family now has a first-pass YAML taxonomy for invoice-ready, invoice-due, receipt-issued, payment-confirmed, overdue-billing, and generic invoice update signals
- INVOICE also carries a family-specific Phase 3 intake override so usable invoice scrubbed text can still be classified even when the shared scrubber marks the message failed under ORDER-biased completeness rules
- INVOICE still needs mailbox-sampled refinement and active template coverage, but it now resolves real Phase 3 profiles instead of only failing closed

Current SECURITY integration:

- [src/email_node/pipeline/security_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/security_flow.py) now provides the initial thin shared-core runner for the `security` family
- [src/email_node/flow_families/security/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/security/runtime.py) wires the shared scrub, profile-detection, template, decision, persistence, and action-gating layers together with placeholder family handlers
- the SECURITY family now has a first-pass YAML taxonomy for security-alert, suspicious-login, password-reset, identity-verification, MFA-code, new-device-login, and generic security notice signals
- SECURITY also carries a family-specific Phase 3 intake override so usable security scrubbed text can still be classified even when the shared scrubber marks the message failed under ORDER-biased completeness rules
- SECURITY still needs mailbox-sampled refinement and active template coverage, but it now resolves real Phase 3 profiles instead of only failing closed

Current SHIPMENT integration:

- [src/email_node/pipeline/shipment_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/shipment_flow.py) now provides the initial thin shared-core runner for the `shipment` family
- [src/email_node/flow_families/shipment/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/shipment/runtime.py) wires the shared scrub, profile-detection, template, decision, persistence, and action-gating layers together with placeholder family handlers
- the SHIPMENT family is still an empty-shell detector at this stage, but the YAML contract, runtime paths, smoke coverage, and shared-core runner are now in place for the next taxonomy task

Why this exists:

- create a real shared package boundary before family-specific configs are extracted
- preserve existing ORDER output contracts while enabling later migration tasks
- keep Phase 2 through Phase 7 execution order and aggregation consistent across future flow families

Not migrated yet:

- active template coverage for ACTION_REQUIRED
- shared generic prompt strategy across all families
