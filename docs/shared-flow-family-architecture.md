# Shared Flow-Family Architecture

This document is the high-level reference for the shared email-flow model in Hexe Email Node.

Use this document to understand:

- how the shared pipeline is structured end to end
- which phases are owned by the shared core
- where each flow family plugs in custom logic
- how runtime YAML config, templates, probation state, persistence, and downstream actions fit together

For rollout sequencing and maturity tracking across families, see:

- [multi-family-rollout-plan.md](/home/dan/Projects/HexeEmail/docs/multi-family-rollout-plan.md)

For the lower-level migration history of the shared core package, see:

- [shared-email-pipeline-core.md](/home/dan/Projects/HexeEmail/docs/shared-email-pipeline-core.md)

## Architecture Goal

The target architecture is a shared pipeline shell with family-owned behavior at the policy and content layers.

That means:

- the shared core owns the phase order, result aggregation, common contracts, and reusable mechanics
- each family owns its own taxonomy, heuristics, templates, validation policy, decision thresholds, and downstream action semantics
- new families should be added by supplying family config and runtime hooks, not by cloning the ORDER implementation

## Flow Families

Current family ids:

- `order`
- `action_required`
- `financial`
- `invoice`
- `security`
- `shipment`

Current family runtime YAML entrypoints:

- [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)
- [runtime/flow_families/action_required/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/family.yaml)
- [runtime/flow_families/financial/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/financial/family.yaml)
- [runtime/flow_families/invoice/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/invoice/family.yaml)
- [runtime/flow_families/security/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/security/family.yaml)
- [runtime/flow_families/shipment/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/shipment/family.yaml)

Current schema for those YAML files:

- [flow-family-config.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/flow-family-config.schema.json)

## Shared Core Boundary

The shared core package lives under:

- [src/email_node/shared_pipeline_core](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core)

It currently owns:

- family config loading in [families.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/families.py)
- YAML parsing and schema-backed translation in [family_yaml.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/family_yaml.py)
- shared Phase 1 interface in [phase1.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/phase1.py)
- shared orchestration in [pipeline.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/pipeline.py)
- shared scrub execution in [scrub_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/scrub_engine.py)
- shared profile detection mechanics in [profile_detector.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/profile_detector.py)
- shared template loading and execution in [template_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/template_engine.py)
- shared probation helpers in [probation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/probation.py)
- shared validation in [validation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/validation.py)
- shared decisioning in [decision.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/decision.py)
- shared persistence in [persistence.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/persistence.py)
- shared action authorization and routing mechanics in [actions.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/actions.py)
- shared reporting in [reporting.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/reporting.py)

The practical rule is:

- shared core owns how phases connect
- families own what each phase means

## End-To-End Phase Model

The current shared pipeline order is implemented in:

- [pipeline.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/pipeline.py)

The execution sequence is:

1. Phase 1: normalized email input is handed to the family flow
2. Phase 2: the family scrubber produces scrubbed text, links, and scrub diagnostics
3. Phase 3: the family detector resolves the best matching profile and confidence
4. Phase 4: the family template engine attempts deterministic extraction
5. Probation hook: the family may generate, reuse, or apply probation templates
6. Phase 6: a shared decision engine turns the extraction result into a terminal decision
7. Phase 7: persistence writes a family-scoped structured output
8. Action gate: downstream actions are allowed or blocked
9. Action router: action intents are resolved from family policy
10. Action handlers: record writes, notifications, and follow-up actions are constructed
11. Reporting: a family report is assembled from the phase results

There is no shared Phase 5 object in the public output right now.

Instead:

- validation is executed inside the Phase 4 template engine
- its effects are reflected in `phase4.field_diagnostics`, `phase4.stage_statuses`, and confidence values

## Per-Phase Responsibilities

### Phase 1

Phase 1 is the normalized-email seam. The shared interface lives in:

- [phase1.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/phase1.py)

Responsibilities:

- fetch or receive normalized email content
- standardize message metadata
- provide consistent input to family Phase 2 scrubbers

Phase 1 is still provider-facing and service-facing, not family-specific.

### Phase 2

Phase 2 is the scrubber stage.

Shared mechanics:

- [scrub_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/scrub_engine.py)

Family inputs:

- `heuristics` block in each family YAML
- family scrubber class inside the family runtime module

Responsibilities:

- remove decorative or non-transactional content
- preserve transactional anchors
- extract candidate action links
- produce `scrub_status`, `scrubbed_text`, normalized lines, extracted links, and diagnostics

Current family behavior:

- `order`, `action_required`, `financial`, and `shipment` use the shared scrub intake directly
- `invoice` and `security` accept some scrub outputs even when the shared scrubber marks them failed, as long as usable text still exists

### Phase 3

Phase 3 is profile detection.

Shared mechanics:

- [profile_detector.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/profile_detector.py)

Family inputs:

- `profiles.taxonomy`
- `profiles.known_vendor_identities`
- `profiles.rules`
- any family-specific Phase 3 intake override in the family runtime

Responsibilities:

- build candidates from subject, scrubbed text, sender domain, and vendor hints
- score candidates with family weights
- apply conflicts or downgrades
- choose the resolved profile, confidence, and diagnostics

This phase is where most family identity lives.

### Phase 4

Phase 4 is template execution.

Shared mechanics:

- [template_engine.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/template_engine.py)

Family inputs:

- family-scoped active template directory
- family template schema version
- family validation policy
- family AI fallback hook behavior

Responsibilities:

- look up an active template for the resolved profile
- execute deterministic extraction methods
- validate extracted fields
- compute extraction confidence
- emit template and field diagnostics

Possible Phase 4 high-level outcomes include:

- `success`
- `partial`
- `unresolved`
- `failed`

### Probation Layer

The probation layer sits between Phase 4 extraction and Phase 6 decisioning.

Shared mechanics:

- [probation.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/probation.py)

Family-owned behavior:

- whether unresolved results should trigger AI generation
- how AI template-generation requests are built
- how probation templates are reapplied
- how promotion to active templates is managed

Current family support:

- `order`: full probation generation, reuse, evaluation, shadow mode, and fallback apply
- `action_required`: same general probation lifecycle as ORDER
- `financial`, `invoice`, `security`, `shipment`: no live probation generation yet; hooks are placeholders

### Phase 6

Phase 6 is the shared decision layer.

Shared mechanics:

- [decision.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/decision.py)

Family inputs:

- family decision thresholds via `decision_policy`

Responsibilities:

- translate extraction status and confidence into a terminal decision
- determine whether structured results persist
- determine whether downstream actions are allowed
- indicate whether manual review is required

Current shared terminal decisions:

- `accept`
- `probation`
- `review_needed`
- `reject`

### Phase 7

Phase 7 is shared persistence plus family-facing action preparation.

Shared persistence mechanics:

- [persistence.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/persistence.py)

Shared action mechanics:

- [actions.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/actions.py)

Responsibilities:

- persist structured outputs to family-scoped runtime paths
- assign persisted trust levels
- authorize or block downstream actions
- resolve family action intents
- call family-specific write or notification handlers

## Shared Contracts

### Shared Decisions

The shared decision contract is:

- `decision`
- `decision_reason`
- `allow_persist_structured_result`
- `allow_downstream_actions`
- `requires_manual_review`
- `confidence`
- `confidence_level`
- `extraction_source`
- `profile_id`
- `diagnostics`

Source:

- [SharedDecisionResult in decision.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/decision.py)

### Shared Persisted Trust Levels

Persisted trust levels are:

- `trusted`
- `partial`
- `review_needed`

Source:

- [SharedOutputPersistenceResult in persistence.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/persistence.py)

Decision-to-trust mapping today:

- `accept` -> `trusted`
- `probation` -> `partial`
- `review_needed` -> `review_needed`
- `reject` -> not persisted

### Shared Action Authorization

The shared action gate currently allows actions when:

- the decision allows downstream actions
- the decision is `accept` or `review_needed`
- the extraction source is active, unless the decision itself is `review_needed`

This means:

- `probation` results are blocked from downstream actions
- `review_needed` results can still surface review-facing intents such as notification or manual review markers

Source:

- [SharedActionGate in actions.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/actions.py)

## Runtime Layout

Each family owns a runtime subtree under:

- [runtime/flow_families](/home/dan/Projects/HexeEmail/runtime/flow_families)

Typical family-owned paths:

- `templates/`
- `probation/templates/`
- `probation/state/`
- `probation/evaluations/`
- `probation/shadow/`
- `outputs/trusted/`
- `outputs/partial/`
- `outputs/review_needed/`
- `reports/`
- `analysis/`

ORDER keeps one compatibility exception:

- it still writes ad hoc reports under [runtime/order_flow_logs/ad_hoc_reports](/home/dan/Projects/HexeEmail/runtime/order_flow_logs/ad_hoc_reports)
- it still keeps legacy output compatibility in [runtime/order_outputs](/home/dan/Projects/HexeEmail/runtime/order_outputs)

That compatibility layer exists so the migration did not break existing ORDER tooling.

## Family Extension Points

Every family plugs into the shared core through:

- a runtime class under `src/email_node/flow_families/<family>/runtime.py`
- YAML config under `runtime/flow_families/<family>/family.yaml`
- thin wrappers for heuristics, profiles, validation, decision, and action routing

The most important extension points are:

- Phase 2 scrub heuristic pack
- Phase 3 candidate generation and scoring
- Phase 3 intake override if scrub semantics differ from ORDER-style mail
- Phase 4 template schema version and registry root
- probation template request mapping and reuse behavior
- decision thresholds
- action routing policy
- family-specific action handler implementations

## Current Family State

### ORDER

Maturity:

- most complete family
- active templates are live
- probation generation and reuse are live
- real downstream handlers are live

Special behavior:

- AI template generation for unresolved cases
- probation reuse and promotion
- record writing, notification generation, and tracking monitor requests

### ACTION_REQUIRED

Maturity:

- second-most complete family
- probation generation and reuse are live
- active template coverage is still limited
- downstream handlers are still placeholder queue results rather than final family-owned integrations

Special behavior:

- broader taxonomy than ORDER in terms of operational/account workflows
- follow-up intents include reminder and priority concepts in addition to manual review

### FINANCIAL

Maturity:

- shared-core skeleton complete
- first-pass YAML taxonomy complete
- smoke-tested
- no active templates yet
- no live probation flow yet
- downstream actions are placeholder queue results

### INVOICE

Maturity:

- shared-core skeleton complete
- first-pass YAML taxonomy complete
- smoke-tested
- no active templates yet
- no live probation flow yet
- downstream actions are placeholder queue results

Special behavior:

- Phase 3 intake override accepts useful scrubbed text even when the shared scrubber marked the message failed

### SECURITY

Maturity:

- shared-core skeleton complete
- first-pass YAML taxonomy complete
- smoke-tested
- no active templates yet
- no live probation flow yet
- downstream actions are placeholder queue results

Special behavior:

- Phase 3 intake override accepts useful scrubbed text even when the shared scrubber marked the message failed

### SHIPMENT

Maturity:

- shared-core skeleton complete
- first-pass YAML taxonomy complete
- smoke-tested
- no active templates yet
- no live probation flow yet
- downstream actions are placeholder queue results

Special behavior:

- initial smoke coverage did not require a Phase 3 intake override

## Reporting Model

Family reports are built with:

- [reporting.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/reporting.py)

The shared report format includes:

- `flow_family`
- `output_schema_family`
- `phase1`
- `phase2`
- `phase3`
- `phase4`
- `phase6`
- `phase7`
- `action_gate`
- `action_router`
- family action results
- `report_summary`

The report builder also renders:

- phase-by-phase status
- persistence summary
- action summary
- diagnostics summary

## Operator Mental Model

The simplest way to think about the system now is:

1. label routing chooses a family
2. the family runtime plugs family logic into the shared core
3. the shared core runs the same phase order for every family
4. family YAML and runtime hooks decide how detection, extraction, probation, and actions behave
5. shared decision, persistence, and reporting normalize the outcomes

## Related Documents

Detailed family references:

- [Email Processing Pipeline (ORDER Flow).md](/home/dan/Projects/HexeEmail/docs/Email%20Processing%20Pipeline%20%28ORDER%20Flow%29.md)
- [order-pattern-probation-lifecycle.md](/home/dan/Projects/HexeEmail/docs/order-pattern-probation-lifecycle.md)
- [flow-family-action-matrix.md](/home/dan/Projects/HexeEmail/docs/flow-family-action-matrix.md)
- [flow-family-terminal-outcomes.md](/home/dan/Projects/HexeEmail/docs/flow-family-terminal-outcomes.md)
- [flow-family-worked-examples.md](/home/dan/Projects/HexeEmail/docs/flow-family-worked-examples.md)

Family-specific references added by the family documentation batch:

- [order-family-reference.md](/home/dan/Projects/HexeEmail/docs/order-family-reference.md)
- [action-required-family-reference.md](/home/dan/Projects/HexeEmail/docs/action-required-family-reference.md)
- [planned-family-references.md](/home/dan/Projects/HexeEmail/docs/planned-family-references.md)
