# Flow-Family YAML Configuration

Flow-family declarative configuration now lives in validated YAML files under:

- [runtime/flow_families/order/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/order/family.yaml)
- [runtime/flow_families/action_needed/family.yaml](/home/dan/Projects/HexeEmail/runtime/flow_families/action_needed/family.yaml)

The shared schema for these files is:

- [flow-family-config.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/flow-family-config.schema.json)

The shared loader and builders live in:

- [family_yaml.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/family_yaml.py)
- [families.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/families.py)

## What Belongs In YAML

Keep declarative family data in YAML:

- family identity
- runtime-owned directory paths
- scrub heuristics
- profile taxonomy
- profile rules, weights, thresholds, and conflict handling
- validation thresholds and field policy
- decision thresholds
- action-routing intents

## What Stays In Python

Keep code-owned behavior in Python:

- phase engines
- family runtime orchestration
- probation generation and application behavior
- downstream handlers
- anything that needs imports, custom code, or I/O behavior

The family modules under [src/email_node/flow_families](/home/dan/Projects/HexeEmail/src/email_node/flow_families) are now thin wrappers around YAML-backed config.

## Edit Workflow

1. Update the target family YAML file.
2. Validate the shape against [flow-family-config.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/flow-family-config.schema.json).
3. Run focused regression tests:
   - `tests/test_flow_family_yaml.py`
   - ORDER-related tests if changing the `order` family
4. Smoke-test the affected flow family if behavior changed.

## Runtime Reload Expectations

Family YAML is loaded at runtime when the shared family config and policy packs are built.

Practical expectation:

- test runs pick up YAML changes immediately
- long-running app processes should be restarted after changing family YAML

## Migration Notes

- `order` keeps its runtime Phase 3 override file at [runtime/order_profile_rules.json](/home/dan/Projects/HexeEmail/runtime/order_profile_rules.json) through `profiles.rules_override_path`
- `action_needed` now uses the normalized family-scoped runtime layout:
  - `runtime/flow_families/action_needed/templates`
  - `runtime/flow_families/action_needed/probation/...`
  - `runtime/flow_families/action_needed/outputs`
  - `runtime/flow_families/action_needed/reports`

## Rule Of Thumb

If a change is something an operator or maintainer should be able to tune without editing Python, it probably belongs in family YAML.
