# Pattern Generation

This document describes the node-local pattern generation flow for creating Phase 4 family extraction templates with the AI node.

## Main components

Pattern generation code lives under:

- [src/email_node/patterns](/home/dan/Projects/HexeEmail/src/email_node/patterns)

Key modules:

- [order_ai_template_request_mapper.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/order_ai_template_request_mapper.py)
  Deterministic mapper from unresolved Phase 4 `ai_template_hook` payloads into `PatternGenerationRequest`.
- [action_required_ai_template_request_mapper.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/action_required_ai_template_request_mapper.py)
  Deterministic mapper from unresolved ACTION_REQUIRED Phase 4 `ai_template_hook` payloads into `PatternGenerationRequest`.
- [pattern_generation_request.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_request.py)
  Strict request contract for the AI prompt input.
- [pattern_generation_response.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_response.py)
  Strict Phase 4 template response contract.
- [pattern_generation_client.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_client.py)
  AI-node direct-execution client for `prompt.email.order_pattern_template_creation`.
- [pattern_generation_pipeline.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_pipeline.py)
  JSON parsing, normalization, and schema validation layer.
- [pattern_generation_writer.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_writer.py)
  Draft template writer.
- [pattern_generation_service.py](/home/dan/Projects/HexeEmail/src/email_node/patterns/pattern_generation_service.py)
  End-to-end orchestration over client, pipeline, and writer.

## Runtime prompt

Current AI prompt definitions used by this flow are:

- [runtime/prompts/prompt.email.order_pattern_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.order_pattern_template_creation.json)
- [runtime/prompts/prompt.email.action_required_pattern_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.action_required_pattern_template_creation.json)

The client sends it to the AI node through:

- `POST /api/execution/direct`

The client selects the prompt from `expected_label` and currently supports:

- `ORDER`
- `SHIPMENT`
- `ACTION_REQUIRED`

Each prompt expects a structured extraction-style task family and returns one Phase 4 template JSON object.

## Request contract

The pattern generation request includes:

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

For unresolved family probation generation, these inputs are derived from the Phase 4 `ai_template_hook` plus sender metadata. The mapper keeps `template_id` deterministic for the same profile and vendor shape.

Important validation behavior:

- `template_id` and `profile_id` must be non-empty
- `body_text` must be non-empty
- `expected_label` is normalized to one of `ORDER`, `SHIPMENT`, `ACTION_REQUIRED`, `FINANCIAL`, `INVOICE`, or `SECURITY`
- `body_html` defaults to `""`
- `links_json` defaults to `[]`

## Response contract

The validated response must match the Phase 4 template shape:

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

Current response validation is strict:

- extra top-level keys are rejected
- `template_version` must be `v1`
- `schema_version` must be non-empty and match the selected family prompt's output schema
- `extract` rules are validated against the supported method set already used by the order-template registry

## API route

The internal trigger route is:

- `POST /api/patterns/generate`

Implementation:

- [src/email_node/api/patterns.py](/home/dan/Projects/HexeEmail/src/email_node/api/patterns.py)

Success response:

- `ok`
- `template_id`
- `file_path`

Failure behavior:

- validation or generation failures are returned as HTTP 400 with a deterministic error string

## Family unresolved handoff

Known-profile family emails that reach Phase 4 with `extraction_status = unresolved` or reusable `failed` unresolved hooks can enter the probation-generation path.

The handoff rules are:

- the unresolved result must expose `ai_template_hook`
- global runtime `AI Calls` must be enabled
- if a probation template already exists for the same profile and vendor, the node evaluates it instead of regenerating
- if an active template already exists, the probation template only runs in shadow mode

Current family-specific handoffs:

- ORDER additionally requires runtime `Check Orders`
- ACTION_REQUIRED runs from the ACTION_REQUIRED flow path on `action_required` classifications

This path writes probation templates to family-scoped runtime storage such as:

- [runtime/flow_families/order/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/order/probation/templates)
- [runtime/flow_families/action_required/probation/templates](/home/dan/Projects/HexeEmail/runtime/flow_families/action_required/probation/templates)

## CLI

The local CLI entrypoint is:

- [scripts/generate_pattern.py](/home/dan/Projects/HexeEmail/scripts/generate_pattern.py)

Example:

```bash
python scripts/generate_pattern.py --input sample.json
```

Optional flags:

- `--target-api-base-url`
- `--allow-overwrite`

## Output location

Generated draft templates are written to:

- [src/email_node/patterns/draft](/home/dan/Projects/HexeEmail/src/email_node/patterns/draft)

Writer behavior:

- file name is `{template_id}.json`
- output is pretty JSON
- overwrite is blocked unless explicitly enabled

## Diagnostics

Pattern generation logs include:

- safe request metadata
- truncated raw AI response preview
- schema validation failures
- saved output path

Sensitive behavior:

- body text and HTML are not logged by default
- full raw response capture is opt-in through the client debug flag

## Tests

Focused and aggregate coverage lives in:

- [tests/test_pattern_generation_request.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation_request.py)
- [tests/test_pattern_generation_response.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation_response.py)
- [tests/test_pattern_generation_client.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation_client.py)
- [tests/test_pattern_generation_pipeline.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation_pipeline.py)
- [tests/test_pattern_generation_writer.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation_writer.py)
- [tests/test_pattern_generation_service.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation_service.py)
- [tests/test_pattern_generation_api.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation_api.py)
- [tests/test_generate_pattern_script.py](/home/dan/Projects/HexeEmail/tests/test_generate_pattern_script.py)
- [tests/test_pattern_generation.py](/home/dan/Projects/HexeEmail/tests/test_pattern_generation.py)
