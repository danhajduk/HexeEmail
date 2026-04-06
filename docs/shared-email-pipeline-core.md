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

Current flow families:

- `order`
- `action_required`

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

Current ACTION_REQUIRED integration:

- [src/email_node/pipeline/action_required_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/action_required_flow.py) now provides an initial thin shared-core runner for the `action_required` family
- [src/email_node/flow_families/action_required/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/runtime.py) wires the shared scrub, profile-detection, template, probation, decision, persistence, and action-gating layers together with placeholder downstream action handlers
- the ACTION_REQUIRED family now has unresolved-template AI handoff, probation-state reuse, and low-confidence probation fallback behavior, but it still does not have active template coverage or family-owned downstream actions
- [src/email_node/patterns/probation_evaluator.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_evaluator.py), [src/email_node/patterns/probation_metrics.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_metrics.py), [src/email_node/patterns/probation_policy.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_policy.py), and [src/email_node/patterns/probation_promotion.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/probation_promotion.py) now thinly wrap the shared probation subsystem in [src/email_node/shared_pipeline_core/probation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/probation.py)
- ORDER still owns its current route-selection policy and downstream action handlers

Why this exists:

- create a real shared package boundary before family-specific configs are extracted
- preserve existing ORDER output contracts while enabling later migration tasks
- keep Phase 2 through Phase 7 execution order and aggregation consistent across future flow families

Not migrated yet:

- active template coverage for ACTION_REQUIRED
- shared generic prompt strategy across all families
