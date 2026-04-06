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

## Flow-Family-Specific Modules

Flow-family modules live under:

- [src/email_node/flow_families/order](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order)
- [src/email_node/flow_families/action_needed](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_needed)

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
- [runtime/flow_families/action_needed/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_needed/family.yaml)
- ORDER Phase 3 override compatibility file:
  - [runtime/order_profile_rules.json](/home/dan/Projects/HexeEmail/runtime/order_profile_rules.json)

Current code-owned family config layout:

- thin ORDER wrappers:
  - [src/email_node/flow_families/order/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/heuristics.py)
  - [src/email_node/flow_families/order/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/profiles.py)
  - [src/email_node/flow_families/order/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/validation.py)
  - [src/email_node/flow_families/order/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/decision.py)
  - [src/email_node/flow_families/order/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/order/action_routing.py)
- thin ACTION_NEEDED wrappers:
  - [src/email_node/flow_families/action_needed/heuristics.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_needed/heuristics.py)
  - [src/email_node/flow_families/action_needed/profiles.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_needed/profiles.py)
  - [src/email_node/flow_families/action_needed/validation.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_needed/validation.py)
  - [src/email_node/flow_families/action_needed/decision.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_needed/decision.py)
  - [src/email_node/flow_families/action_needed/action_routing.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_needed/action_routing.py)

## Template Directory Layout

Active templates are now family-scoped under runtime:

- ORDER active templates:
  - [runtime/flow_families/order/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/order/templates)
- ORDER probation templates:
  - [runtime/flow_families/order/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/templates)
  - [runtime/flow_families/order/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/state)
  - [runtime/flow_families/order/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/evaluations)
  - [runtime/flow_families/order/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/shadow)

Current ACTION_NEEDED template root from family config:

- [runtime/flow_families/action_needed/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_needed/templates)
- [runtime/flow_families/action_needed/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_needed/probation/templates)
- [runtime/flow_families/action_needed/probation/state](/home/dan/Projects/HexeEmail/runtime/flow_families/action_needed/probation/state)
- [runtime/flow_families/action_needed/probation/evaluations](/home/dan/Projects/HexeEmail/runtime/flow_families/action_needed/probation/evaluations)
- [runtime/flow_families/action_needed/probation/shadow](/home/dan/Projects/HexeEmail/runtime/flow_families/action_needed/probation/shadow)

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

ACTION_NEEDED currently does not attempt probation generation yet. Its skeleton uses a pass-through probation hook.

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

## How ACTION_NEEDED Plugs In

Public runner:

- [src/email_node/pipeline/action_needed_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/action_needed_flow.py)

Family runtime:

- [src/email_node/flow_families/action_needed/runtime.py](/home/dan/Projects/HexeEmail/src/email_node/flow_families/action_needed/runtime.py)

Current skeleton behavior:

- uses shared scrub/profile/template/decision/persistence/action-gate layers
- loads ACTION_NEEDED family heuristic/profile/policy packs
- uses placeholder downstream action results
- proves that a second family can execute through the same shared orchestration path

Current limitations:

- scrub completeness is still tuned around ORDER-style transactional signals
- ACTION_NEEDED does not yet have active template coverage
- probation generation and promotion are not yet implemented for ACTION_NEEDED
- placeholder downstream actions need to be replaced with family-owned handlers

## Practical Rule

When adding or changing behavior:

- put reusable mechanics in the shared core
- put family-specific thresholds, heuristics, taxonomies, and routing in family YAML
- keep public family runners thin
- keep runtime-owned mutable state under `runtime/flow_families/<family>/...`
