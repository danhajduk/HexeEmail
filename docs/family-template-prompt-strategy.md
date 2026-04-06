# Family Template Prompt Strategy

This document records the prompt-layer strategy for AI-generated Phase 4 templates across flow families.

## Task 322 Evaluation

Question:

- can one generic family template-creation prompt cover multi-family AI template generation?

Current answer:

- yes, with constraints

## Why A Shared Prompt Is Viable

The current prompt contracts for:

- [prompt.email.order_pattern_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.order_pattern_template_creation.json)
- [prompt.email.action_required_pattern_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.action_required_pattern_template_creation.json)

already show that most of the contract is shared:

- same task family: `task.structured_extraction`
- same high-level role: deterministic Phase 4 template author
- same execution policy and provider preferences
- same request inputs:
  - `template_id`
  - `profile_id`
  - `template_version`
  - `vendor_identity`
  - `expected_label`
  - `from_name`
  - `from_email`
  - `subject`
  - `received_at`
  - `body_text`
  - `body_html`
  - `links_json`
- same extract-rule method family:
  - `regex`
  - `line_contains`
  - `line_after`
  - `between_markers`
  - `all_matches`
  - `first_match`
  - `link_by_label`
  - `link_by_type`
- same top-level response structure:
  - `schema_version`
  - `template_id`
  - `profile_id`
  - `template_version`
  - `enabled`
  - `match`
  - `extract`
  - `required_fields`
  - `confidence_rules`
  - `post_process`

The code already leans generic too:

- [PatternGenerationRequest](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_request.py) accepts `ORDER`, `SHIPMENT`, `ACTION_REQUIRED`, `FINANCIAL`, `INVOICE`, and `SECURITY`
- [PatternGenerationResponse](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_response.py) validates the common template envelope instead of a family-specific subtype
- each runtime family already owns its own Phase 4 schema version:
  - `order-phase4-template.v1`
  - `action-required-phase4-template.v1`
  - `financial-phase4-template.v1`
  - `invoice-phase4-template.v1`
  - `security-phase4-template.v1`
  - `shipment-phase4-template.v1`

That means the main divergence is not the outer prompt contract. It is the family-specific guidance carried inside it.

## What Must Stay Family-Specific

A shared prompt only works if these values are provided per family:

- output `schema_version`
- family name / label context
- family-specific field guidance
- family-specific recommended required fields
- family-specific example extraction targets
- optional family-specific match guidance

Examples:

- `order` and `shipment` care about things like `order_number`, `tracking_number`, `status`, and action links
- `action_required` cares about `action_url`, `verification_code`, `due_date`, and issue summary
- `security` may need verification or alert fields that do not belong in invoice-style templates
- `financial` and `invoice` may overlap, but still differ in whether the main object is a statement, invoice, receipt, or billing notice

## What The Mailbox Samples Suggest

The family sample artifacts support using one generic prompt envelope:

- [family-mailbox-sample-analysis.md](/home/dan/Projects/HexeEmail/docs/family-mailbox-sample-analysis.md)

Key takeaway:

- family differences are real, but they mostly affect field guidance and schema strings, not the outer mechanics of prompt execution

This makes a shared prompt contract practical, while still allowing family-owned guidance blocks.

## Recommendation

Use one shared prompt contract:

- `prompt.email.family_pattern_template_creation`

Implemented prompt artifact:

- [prompt.email.family_pattern_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.family_pattern_template_creation.json)

And feed it family-owned inputs for:

- `template_schema_version`
- `flow_family`
- `field_guidance_json`
- `match_guidance_json`
- `allowed_transform_names`

This keeps:

- one AI execution contract
- one general output validator shape
- one prompt-sync artifact to maintain

while still preserving family-specific extraction semantics.

## Constraints

The shared prompt is only safe if:

- every family continues to use the same extract-rule method model
- every family stays inside the same top-level template envelope
- family-specific schema versions are passed explicitly
- the prompt is strict about not inventing unsupported fields or methods

If a future family needs a fundamentally different Phase 4 contract, that family should get its own prompt instead of stretching the shared prompt too far.

## Decision

For the current family set, the shared prompt is viable.

That means the next implementation step should be:

- define and add the generic prompt contract

instead of creating separate new prompt files for `financial`, `invoice`, `security`, and `shipment`.
