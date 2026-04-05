# Node-Owned JSON Schemas

This folder contains the Hexe Email Node JSON schemas that are owned by this repository.

These schemas are derived from implemented code and runtime contracts, not planning notes.

## Coverage

The current schema set covers:

- core node request, response, notification, and persisted-state models from `src/models.py`
- Gmail provider request, response, persisted-state, training, and pipeline models from `src/providers/gmail/models.py`
- runtime prompt definition files under `src/runtime_prompts/`
- structured output schemas embedded in the runtime prompt definitions
- Gmail order-template JSON files validated by `src/providers/gmail/order_template_registry.py`

## Files

- [node-api-model-catalog.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/node-api-model-catalog.schema.json)
  Core node model catalog generated from `src/models.py`. Individual schemas live under `$defs`.

- [gmail-provider-model-catalog.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/gmail-provider-model-catalog.schema.json)
  Gmail provider model catalog generated from `src/providers/gmail/models.py`. Individual schemas live under `$defs`.

- [runtime-prompt-definition.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/runtime-prompt-definition.schema.json)
  Generic schema for the node-owned prompt definition files in `src/runtime_prompts/`.

- [prompt.email.classifier.output.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/prompt.email.classifier.output.schema.json)
  Structured output schema for `prompt.email.classifier`.

- [prompt.email.action_decision.output.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/prompt.email.action_decision.output.schema.json)
  Structured output schema for `prompt.email.action_decision`.

- [prompt.email.summarization.output.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/prompt.email.summarization.output.schema.json)
  Structured output schema for `prompt.email.summarization`.

- [gmail-order-template.schema.json](/home/dan/Projects/HexeEmail/docs/schemas/gmail-order-template.schema.json)
  Contract for the JSON templates stored under `runtime/order_templates/`.

## Notes

- The two catalog files are valid JSON Schema documents that use `$defs` to hold the individual model schemas.
- Runtime artifacts such as local OAuth session files, token records, mailbox state files, and stored-message records are covered through the generated model catalogs.
- This folder now covers the node-owned schema surfaces I could verify from the current repository state. It does not attempt to mirror Core-owned schemas.
