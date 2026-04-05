# Configuration

This document is the repo-level configuration source of truth for the Hexe Email Node.

## Typed config entrypoint

Runtime configuration is loaded through [config.py](/home/dan/Projects/HexeEmail/src/config.py) via `AppConfig`.

Important config groups currently present:

- Core/node identity and networking
- runtime directory and prompt definition paths
- Gmail polling and local classification thresholds
- provider enablement flags

## Important environment-backed settings

Current high-signal settings include:

- `CORE_BASE_URL`
- `NODE_NAME`
- `NODE_TYPE`
- `NODE_SOFTWARE_VERSION`
- `NODE_NONCE`
- `RUNTIME_DIR`
- `PROMPT_DEFINITION_DIR`
- `API_PORT`
- `UI_PORT`
- `GMAIL_STATUS_POLL_INTERVAL_SECONDS`
- `GMAIL_STATUS_POLL_ON_STARTUP`
- `GMAIL_FETCH_POLL_ON_STARTUP`
- `GMAIL_LOCAL_CLASSIFICATION_THRESHOLD`
- `GMAIL_TRAINING_BOOTSTRAP_THRESHOLD`

## Provider configuration

Provider config shape currently lives in:

- [config.py](/home/dan/Projects/HexeEmail/src/config.py)
- [src/providers/gmail/config_store.py](/home/dan/Projects/HexeEmail/src/providers/gmail/config_store.py)

Gmail OAuth setup specifics are documented in:

- [gmail-oauth-setup-guide.md](/home/dan/Projects/HexeEmail/docs/gmail-oauth-setup-guide.md)

## Operator-editable versus node-managed configuration

Operator-managed:

- `.env`
- selected provider config through node/UI APIs
- operator config persisted under `runtime/`

Node-managed:

- trust material
- onboarding/session state
- Gmail provider state stores
- local training/model metadata
- runtime task state

## Configuration verification

Config validation behavior is covered by:

- [test_config.py](/home/dan/Projects/HexeEmail/tests/test_config.py)
- Gmail config tests under [tests/](/home/dan/Projects/HexeEmail/tests)
