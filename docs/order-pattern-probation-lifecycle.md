# ORDER Pattern Probation Lifecycle

This document describes the probation lifecycle for ORDER Phase 4 templates generated from unresolved known-profile emails.

## Flow

1. A known-profile ORDER email reaches Phase 4 and no active template matches.
2. The unresolved result emits `ai_template_hook`.
3. The ORDER pipeline maps that hook into the pattern-generation flow.
4. The generated template is saved into probation storage.
5. A probation state record is created.
6. Later matching emails evaluate that probation template instead of regenerating it.
7. When an active template exists, the probation template runs in shadow mode only.
8. Promotion policy decides whether the template should remain on probation, be refined, be rejected, or become active.

## Thresholds

Current promotion thresholds:

- minimum sample count: `5`
- required field success rate: `>= 0.90`
- high-requires success rate: `>= 0.80`
- hard failure count: `<= 1`

## Shadow Mode

When an active template already resolves the email:

- the active template remains authoritative
- the probation template evaluates in the background
- comparison output is stored for operator review
- no downstream production behavior changes because of the probation template

## Directory Structure

- probation templates: `src/email_node/patterns/probation/`
- probation state: `src/email_node/patterns/probation_state/`
- probation evaluations: `src/email_node/patterns/probation_evaluations/`
- probation shadow comparisons: `src/email_node/patterns/probation_shadow/`
- active templates: `runtime/order_templates/`

## Operator Surfaces

- API:
  - `GET /api/patterns/probation`
  - `GET /api/patterns/probation/{template_id}`
  - `GET /api/patterns/probation/{template_id}/evaluations`
- CLI:
  - `python scripts/probation_tools.py state <template_id>`
  - `python scripts/probation_tools.py evaluations <template_id>`
  - `python scripts/probation_tools.py eligibility <template_id>`

## Operator Expectations

- first unresolved known-profile email creates a probation template
- repeated matching emails reuse and evaluate that template
- probation evaluation does not trigger downstream order actions
- promotion is threshold-based and leaves probation history in place
