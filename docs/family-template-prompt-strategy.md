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

Related recovery prompt:

- [prompt.email.identifier_recovery_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.identifier_recovery_template_creation.json)

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

## Practical Guardrails

In practice, the shared prompt works best when the prompt and the client enforce the same narrow contract.

Current guardrails are:

- `match` is limited to `vendor_identity`
- extract rules must be explicit objects with `method`
- transform arrays must use `transforms`
- the client performs narrow normalization for common model drift before schema validation

Current client-side repairs:

- strip extra `match` keys such as `from_email`, `from_email_domain`, `subject_contains`, and `subject_contains_any`
- rewrite singular `transform` into `transforms`
- unwrap text-wrapped JSON responses

This lets the prompt remain strict without forcing the node to reject every otherwise-usable response for small naming drift.

## Constraints

The shared prompt is only safe if:

- every family continues to use the same extract-rule method model
- every family stays inside the same top-level template envelope
- family-specific schema versions are passed explicitly
- the prompt is strict about not inventing unsupported fields or methods

If a future family needs a fundamentally different Phase 4 contract, that family should get its own prompt instead of stretching the shared prompt too far.

## Identifier Recovery Prompt

Use `prompt.email.identifier_recovery_template_creation` for high-confidence ORDER or SHIPMENT emails where normal extraction failed because the useful identifier is hidden outside visible text. Examples include order numbers in dynamic image URLs, action URLs behind redirect links, tracking identifiers in query parameters, compound URL parameter segments, or status values rendered into images.

This prompt returns a probation proposal, not a trusted executable template. The proposal includes evidence, a proposed template, validation steps, and any parser capabilities that are required before the rule can run deterministically. It should learn reusable structural patterns from labels, HTML attributes, query keys, redirect destinations, and nearby context rather than overfitting to one sender or one exact URL. That keeps AI useful for discovering the pattern while preserving review before new extraction methods such as HTML attribute query parsing, parent-link redirect parsing, compound parameter parsing, or OCR become production behavior.

## Expected Failure Cases

A shared prompt should not be judged only by whether it can produce a template for every message.

Healthy failure cases include:

- mailbox digests that are family-labeled but not good reusable template sources
- messages that are too weak, too broad, or too presentation-specific for deterministic extraction
- samples whose best interpretation would require family-specific schema elements we do not currently support

That means a mixed live result such as:

- strong family-specific transactional samples succeeding
- weaker digest-style or non-template-fit samples failing

is often the correct operational behavior, not a prompt defect.

## Decision

For the current family set, the shared prompt is viable.

That means the next implementation step should be:

- define and add the generic prompt contract

instead of creating separate new prompt files for `financial`, `invoice`, `security`, and `shipment`.
