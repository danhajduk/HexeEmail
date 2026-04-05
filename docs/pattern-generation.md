# Pattern Generation

This document describes the node-local pattern generation flow for creating Phase 4 ORDER extraction templates with the AI node.

## Main components

Pattern generation code lives under:

- [src/email_node/patterns](/home/dan/Projects/HexeEmail/src/email_node/patterns)

Key modules:

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

The AI prompt definition used by this flow is:

- [runtime/prompts/prompt.email.order_pattern_template_creation.json](/home/dan/Projects/HexeEmail/runtime/prompts/prompt.email.order_pattern_template_creation.json)

The client sends it to the AI node through:

- `POST /api/execution/direct`

The prompt currently expects a structured extraction-style task family and returns one Phase 4 template JSON object.

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

Important validation behavior:

- `template_id` and `profile_id` must be non-empty
- `body_text` must be non-empty
- `expected_label` is normalized to `ORDER` or `SHIPMENT`
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
- `schema_version` must be `order-phase4-template.v1`
- `template_version` must be `v1`
- `match.vendor_identity` is required by the response contract
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
