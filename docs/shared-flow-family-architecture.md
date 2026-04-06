# Shared Flow-Family Architecture

This document describes the current split between the shared email pipeline core and the flow-family-specific modules that plug into it.

## Goal

The migration target is a pipeline where:

- the shared core owns phase orchestration and reusable mechanics
- each flow family supplies its own heuristics, profiles, templates, policies, and downstream actions
- new families can be added without cloning the ORDER implementation

## Shared Core

The shared core lives under:

- [src/email_node/shared_pipeline_core](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core)

It currently owns:

- flow-family config loading in [families.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/families.py)
- YAML schema-backed family config loading in [family_yaml.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/family_yaml.py)
- Phase 1 normalization interface in [phase1.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/phase1.py)
- shared phase orchestration in [pipeline.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/pipeline.py)
- shared scrub engine in [scrub_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/scrub_engine.py)
- shared profile detection engine in [profile_detector.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/profile_detector.py)
- shared template registry and execution in [template_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/template_engine.py)
- shared probation lifecycle helpers in [probation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/probation.py)
- shared validation policy framework in [validation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/validation.py)
- shared decision framework in [decision.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/decision.py)
- shared persistence and action gating in [persistence.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/persistence.py) and [actions.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/actions.py)
- shared report assembly in [reporting.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/reporting.py)
- pack loaders for family policy/config modules:
  - [profile_packs.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/profile_packs.py)
  - [validation_packs.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/validation_packs.py)
  - [decision_packs.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/decision_packs.py)
  - [action_packs.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/action_packs.py)

Shared terminal outcomes currently supported across flow families:

- `accept`
- `probation`
- `review_needed`
- `reject`

`review_needed` is the shared fallback for flows that should not silently disappear on failure. It persists under the family review-needed output bucket and can still surface review-facing intents such as user notification and manual-review markers.

## Flow-Family-Specific Modules

Flow-family modules live under:

- [src/email_node/flow_families/order](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order)
- [src/email_node/flow_families/action_required](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required)
- [src/email_node/flow_families/financial](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial)
- [src/email_node/flow_families/invoice](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice)

Each family is responsible for:

- declarative family YAML under `runtime/flow_families/<family>/family.yaml`
- family runtime wiring
- family-specific downstream actions and output expectations

## Config Directory Layout

Shared family identity is declared through:

- [src/email_node/shared_pipeline_core/families.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/families.py)
- [docs/flow-family-yaml-configuration.md](/home/dan/Projects/HexeEmail/docs/flow-family-yaml-configuration.md)

Current runtime-owned family config layout:

- [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)
- [runtime/flow_families/action_required/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/family.yaml)
- [runtime/flow_families/financial/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/family.yaml)
- [runtime/flow_families/invoice/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/family.yaml)
- ORDER Phase 3 override compatibility file:
  - [runtime/order_profile_rules.json](/home/dan/Projects/HexeEmail/runtime/order_profile_rules.json)

Current code-owned family config layout:

- thin ORDER wrappers:
  - [src/email_node/flow_families/order/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/heuristics.py)
  - [src/email_node/flow_families/order/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/profiles.py)
  - [src/email_node/flow_families/order/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/validation.py)
  - [src/email_node/flow_families/order/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/decision.py)
  - [src/email_node/flow_families/order/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/action_routing.py)
- thin ACTION_REQUIRED wrappers:
  - [src/email_node/flow_families/action_required/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/heuristics.py)
  - [src/email_node/flow_families/action_required/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/profiles.py)
  - [src/email_node/flow_families/action_required/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/validation.py)
  - [src/email_node/flow_families/action_required/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/decision.py)
  - [src/email_node/flow_families/action_required/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/action_routing.py)
- thin FINANCIAL wrappers:
  - [src/email_node/flow_families/financial/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/heuristics.py)
  - [src/email_node/flow_families/financial/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/profiles.py)
  - [src/email_node/flow_families/financial/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/validation.py)
  - [src/email_node/flow_families/financial/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/decision.py)
  - [src/email_node/flow_families/financial/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/financial/action_routing.py)
- thin INVOICE wrappers:
  - [src/email_node/flow_families/invoice/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/heuristics.py)
  - [src/email_node/flow_families/invoice/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/profiles.py)
  - [src/email_node/flow_families/invoice/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/validation.py)
  - [src/email_node/flow_families/invoice/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/decision.py)
  - [src/email_node/flow_families/invoice/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/invoice/action_routing.py)

## Template Directory Layout

Active templates are now family-scoped under runtime:

- ORDER active templates:
  - [runtime/flow_families/order/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/order/templates)
- ORDER probation templates:
  - [runtime/flow_families/order/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/templates)
  - [runtime/flow_families/order/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/state)
  - [runtime/flow_families/order/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/evaluations)
  - [runtime/flow_families/order/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/shadow)

Current ACTION_REQUIRED template root from family config:

- [runtime/flow_families/action_required/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/templates)
- [runtime/flow_families/action_required/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/templates)
- [runtime/flow_families/action_required/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/state)
- [runtime/flow_families/action_required/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/evaluations)
- [runtime/flow_families/action_required/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/shadow)

Current FINANCIAL template root from family config:

- [runtime/flow_families/financial/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/templates)
- [runtime/flow_families/financial/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/probation/templates)
- [runtime/flow_families/financial/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/probation/state)
- [runtime/flow_families/financial/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/probation/evaluations)
- [runtime/flow_families/financial/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/probation/shadow)

Current INVOICE template root from family config:

- [runtime/flow_families/invoice/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/templates)
- [runtime/flow_families/invoice/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/probation/templates)
- [runtime/flow_families/invoice/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/probation/state)
- [runtime/flow_families/invoice/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/probation/evaluations)
- [runtime/flow_families/invoice/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/probation/shadow)

## Probation Reuse Model

Probation lifecycle is shared, but family-owned at the storage and policy edges.

Shared probation mechanics:

- evaluation
- metrics updates
- promotion threshold logic
- shadow comparison helpers

Family-owned probation behavior:

- when probation is attempted
- how AI generation requests are built
- how probation templates are applied back into family extraction results
- where probation templates are promoted

ORDER currently implements that family behavior in:

- [src/email_node/flow_families/order/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/runtime.py)

ACTION_REQUIRED now has the same probation storage, evaluation, promotion, unresolved-template AI handoff, and low-confidence probation fallback shape as ORDER, while still keeping family-specific request mapping and template schema ownership inside the family runtime.

FINANCIAL now uses the shared skeleton plus a first-pass YAML taxonomy. It has family-owned YAML, runtime paths, smoke-tested shared-core wiring, and initial detector coverage for statement-ready, payment-due, payment-received, refund, balance-alert, tax-document, and generic financial update cases. It still does not have active template behavior or mailbox-sampled refinement yet.

INVOICE now uses the shared skeleton plus a first-pass YAML taxonomy. It has family-owned YAML, runtime paths, smoke-tested shared-core wiring, and initial detector coverage for invoice-ready, invoice-due, receipt-issued, payment-confirmed, overdue-billing, and generic invoice update cases. It also has a family-specific Phase 3 intake override for usable invoice scrubbed text. It still does not have active template behavior or mailbox-sampled refinement yet.

## How ORDER Uses The Framework

Public runner:

- [src/email_node/pipeline/order_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_flow.py)

Family runtime:

- [src/email_node/flow_families/order/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/runtime.py)

Current ORDER shape:

- `OrderFlowPipeline` is a thin wrapper
- `OrderFlowRuntime` wires shared phases together with ORDER families, policies, probation behavior, and downstream handlers
- ORDER still keeps its current output contract and live behavior

ORDER-specific pieces still outside shared core:

- ORDER output record format in [src/email_node/pipeline/order_output_handler.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_output_handler.py)
- ORDER downstream order record writing in [src/email_node/orders/order_record_service.py](/home/dan/Projects/HexeEmail/src/email_node/orders/order_record_service.py)
- ORDER notification and tracking handlers in:
  - [src/email_node/actions/user_notification_handler.py](/home/dan/Projects/HexeEmail/src/email_node/actions/user_notification_handler.py)
  - [src/email_node/actions/tracking_monitor_handler.py](/home/dan/Projects/HexeEmail/src/email_node/actions/tracking_monitor_handler.py)

## How ACTION_REQUIRED Plugs In

Public runner:

- [src/email_node/pipeline/action_required_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/action_required_flow.py)

Family runtime:

- [src/email_node/flow_families/action_required/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_required/runtime.py)

Current skeleton behavior:

- uses shared scrub/profile/template/decision/persistence/action-gate layers
- loads ACTION_REQUIRED family heuristic/profile/policy packs
- can build family-specific unresolved-template AI requests and write probation templates under the family runtime paths
- can reuse existing probation templates, evaluate them, and apply them back as low-confidence partial results
- uses placeholder downstream action results
- proves that a second family can execute through the same shared orchestration path
- unresolved or hard-validation outcomes now use the shared `review_needed` contract rather than only failing closed as plain rejects

Current limitations:

- scrub completeness is still tuned around ORDER-style transactional signals
- ACTION_REQUIRED does not yet have active template coverage
- placeholder downstream actions need to be replaced with family-owned handlers

## Practical Rule

When adding or changing behavior:

- put reusable mechanics in the shared core
- put family-specific thresholds, heuristics, taxonomies, and routing in family YAML
- keep public family runners thin
- keep runtime-owned mutable state under `runtime/flow_families/<family>/...`
