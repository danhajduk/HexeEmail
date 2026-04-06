# Multi-Family Rollout Plan

This document tracks the practical rollout path for the shared email flow-family model across:

- `order`
- `action_required`
- `financial`
- `invoice`
- `security`
- `shipment`

It is intentionally implementation-focused. The goal is to make it clear which families are already production-capable, which ones are only scaffolded, and what remaining work moves each family from detector-only coverage to a usable end-to-end flow.

## Rollout Model

Each family is expected to mature through the same stages:

1. Shared-core wiring
2. Declarative YAML config
3. Phase 3 detector coverage
4. Phase 4 template coverage
5. Phase 5 validation tuning
6. Phase 6 decision tuning
7. Phase 7 persistence and downstream actions
8. Probation and AI-assisted template creation where needed
9. Mailbox-sampled refinement
10. Operator documentation and review surfaces

The shared pipeline core already provides the common execution frame. Rollout quality now depends mostly on family-owned taxonomy quality, template coverage, and downstream action ownership.

## Current Family Status

### ORDER

Current maturity:

- shared-core migrated
- YAML-backed config live
- active template coverage live
- AI probation/template generation live
- Phase 6 decisioning live
- Phase 7 persistence and downstream actions live

Current role:

- reference implementation for the full flow-family model
- baseline for probation behavior
- baseline for trusted vs partial vs review-needed output handling

Remaining work:

- continue moving family-specific heuristics into more maintainable runtime data where practical
- keep tightening sampled taxonomy, templates, and downstream actions

### ACTION_REQUIRED

Current maturity:

- shared-core migrated
- YAML-backed config live
- Phase 3 detector coverage live
- AI probation/template generation live
- low-confidence probation fallback live
- shared review-needed fallback live

Current limitations:

- no meaningful active template coverage yet
- downstream actions are still placeholder-level
- taxonomy has been improved, but it still needs broader mailbox-sampled refinement
- scrub/Phase 3 quality is not as mature as ORDER

Next rollout target:

- turn mailbox-sampled categories into stable profiles
- create active templates and promotion paths
- replace placeholder downstream action behavior with family-owned handlers

### FINANCIAL

Current maturity:

- shared-core migrated
- YAML-backed config live
- first-pass Phase 3 detector coverage live
- review-needed fallback live

Current limitations:

- no active templates
- no AI probation/template generation yet
- no family-owned downstream actions
- taxonomy is first-pass only and has not yet been shaped by a 20-30 message mailbox sample

Next rollout target:

- derive taxonomy from real FINANCIAL mail samples
- define high-value profiles worth templating first
- decide which downstream actions should exist versus remain review-only

### INVOICE

Current maturity:

- shared-core migrated
- YAML-backed config live
- first-pass Phase 3 detector coverage live
- family-specific Phase 3 intake override live
- review-needed fallback live

Current limitations:

- no active templates
- no AI probation/template generation yet
- no family-owned downstream actions
- current detector quality is only smoke-tested, not mailbox-calibrated

Next rollout target:

- sample real invoice mail
- tighten invoice-ready, due, receipt, overdue, and payment-confirmed boundaries
- define the minimum structured extraction needed before persistence should become trusted

### SECURITY

Current maturity:

- shared-core migrated
- YAML-backed config live
- first-pass Phase 3 detector coverage live
- family-specific Phase 3 intake override live
- review-needed fallback live

Current limitations:

- no active templates
- no AI probation/template generation yet
- no family-owned downstream security actions
- some security-like messages may still be too generic for the current taxonomy

Next rollout target:

- sample real security mail
- separate informational notices from true action-required security messages
- define safe downstream actions and explicit no-action cases

### SHIPMENT

Current maturity:

- shared-core migrated
- YAML-backed config live
- first-pass Phase 3 detector coverage live
- review-needed fallback live

Current limitations:

- no active templates
- no AI probation/template generation yet
- no family-owned downstream shipment actions
- shipment state modeling has not been stress-tested against enough carriers and retailer mail shapes

Next rollout target:

- sample real shipment mail
- tune delivered, delayed, label-created, shipped, and out-for-delivery boundaries
- decide what should persist immediately versus remain review-needed

## Rollout Sequence

The practical rollout order should stay:

1. `order`
2. `action_required`
3. `financial`
4. `invoice`
5. `security`
6. `shipment`

Why this order:

- `order` already proves the full path
- `action_required` is the closest second family because it already has probation support
- `financial`, `invoice`, `security`, and `shipment` now have shared-core skeletons, but they still need sample-driven calibration before active template work is worth doing

## Shared Gating Rules

A family should not be considered production-capable just because Phase 3 returns a profile. A family is ready for broad use only when:

- detector categories are shaped by real mailbox samples
- Phase 4 has at least minimal active or probation-capable templates
- Phase 5 validation rejects obviously unsafe extraction
- Phase 6 decisions reflect real family semantics
- Phase 7 persistence does not over-trust weak or partial outputs
- downstream action handlers are real, not placeholders
- operator-facing reports clearly expose `accept`, `probation`, `review_needed`, and `reject`

## Family-by-Family Rollout Checklist

### Shared for every new family

- confirm YAML config shape and runtime paths
- collect 20-30 real mailbox samples when available
- derive candidate profiles from scrubbed content
- tune thresholds, sender hints, and signal groups
- define family-specific template schema expectations
- add active template coverage or probation generation
- define review-needed behavior
- define family-owned downstream actions
- add smoke reports and focused regression tests
- document examples and operator expectations

### ORDER and ACTION_REQUIRED hardening

- continue using them as the pattern for probation-capable families
- reduce remaining placeholder behavior in ACTION_REQUIRED
- use the shared prompt strategy only after cross-family feasibility is proven

### FINANCIAL, INVOICE, SECURITY, SHIPMENT expansion

- treat current YAML as seed taxonomy, not final truth
- avoid building many templates before the sample analysis is complete
- prefer review-needed over aggressive trust when template coverage is still thin

## Sample-Driven Tuning Plan

The next rollout step after this document is mailbox-sampled calibration for:

- `financial`
- `invoice`
- `security`
- `shipment`

That work should produce:

- scrubbed-content sample artifacts
- recurring phrase clusters
- sender-domain patterns
- missing categories
- false-positive risks
- recommended YAML changes

These sample artifacts should become the basis for:

- family taxonomy refinement
- template-priority ordering
- decision-policy tuning
- future family-specific AI template-generation prompts if a shared prompt is not viable

Current cross-family sample synthesis:

- [family-mailbox-sample-analysis.md](/home/dan/Projects/HexeEmail/docs/family-mailbox-sample-analysis.md)

## Prompt Strategy Dependency

The next major shared dependency is AI template generation.

Questions that still need to be answered:

- can one generic family template-creation prompt work across all families?
- or do `order`, `action_required`, `financial`, `invoice`, `security`, and `shipment` each need their own prompt contract?

The answer should come after mailbox-sample analysis, not before. The sample set will show whether the output schemas and extraction shapes are close enough to share one prompt safely.

## Review-Needed Rule

Across all families, unresolved or incomplete flows should prefer the shared `review_needed` path when:

- the flow found meaningful transactional signal
- the extraction is not safe enough to trust
- the result should still be surfaced for operator or user review

This avoids silent loss while still preserving trust boundaries.

## Exit Criteria For Broad Rollout

The multi-family rollout should be considered broadly complete only when:

- all six families run through the shared-core pipeline
- all six have mailbox-sampled taxonomy refinement
- all six have explicit Phase 4 strategy
- all six have documented Phase 6 and Phase 7 behavior
- all six have clear operator documentation
- scheduled-task/runtime surfaces reflect the new multi-family world
- the completion notification task is sent through the Core MQTT notification flow

## Related Documents

- [shared-flow-family-architecture.md](/home/dan/Projects/HexeEmail/docs/shared-flow-family-architecture.md)
- [shared-email-pipeline-core.md](/home/dan/Projects/HexeEmail/docs/shared-email-pipeline-core.md)
- [flow-family-yaml-configuration.md](/home/dan/Projects/HexeEmail/docs/flow-family-yaml-configuration.md)
- [Email Processing Pipeline (ORDER Flow).md](/home/dan/Projects/HexeEmail/docs/Email%20Processing%20Pipeline%20%28ORDER%20Flow%29.md)
