# Security And Sensitive State

This document describes the sensitive data handled by the Hexe Email Node and the storage boundaries that matter today.

It is based on the current implementation in:

- [config.py](/home/dan/Projects/HexeEmail/src/config.py)
- [state_store.py](/home/dan/Projects/HexeEmail/src/state_store.py)
- [logging_utils.py](/home/dan/Projects/HexeEmail/src/logging_utils.py)
- [runtime.py](/home/dan/Projects/HexeEmail/src/providers/gmail/runtime.py)
- [config_store.py](/home/dan/Projects/HexeEmail/src/providers/gmail/config_store.py)
- [token_store.py](/home/dan/Projects/HexeEmail/src/providers/gmail/token_store.py)

## Sensitive State Categories

### Core trust material

- [trust_material.json](/home/dan/Projects/HexeEmail/runtime/trust_material.json)
- contains:
  - node trust token
  - operational MQTT credentials
  - paired Core identity
- owner: onboarding/trust lifecycle
- sensitivity: critical

### Gmail OAuth configuration and account secrets

- [provider_config.json](/home/dan/Projects/HexeEmail/runtime/providers/gmail/provider_config.json)
  - contains Gmail client id, redirect uri, and secret reference metadata
- [oauth_state_secret](/home/dan/Projects/HexeEmail/runtime/providers/gmail/oauth_state_secret)
  - protects OAuth state handling
- [accounts](/home/dan/Projects/HexeEmail/runtime/providers/gmail/accounts)
  - includes per-account token records in `*.token.json`
- [oauth_sessions](/home/dan/Projects/HexeEmail/runtime/providers/gmail/oauth_sessions)
  - pending OAuth flow state
- sensitivity: high

### Gmail mailbox data

- [messages.sqlite3](/home/dan/Projects/HexeEmail/runtime/providers/gmail/messages.sqlite3)
- related mailbox snapshots, sender reputation, Spamhaus results, labels, and reports under `runtime/providers/gmail/`
- sensitivity: high
- reason: these files contain user email metadata and potentially message bodies or derived classifier inputs

### Local training artifacts

- [training_model.pkl](/home/dan/Projects/HexeEmail/runtime/providers/gmail/training_model.pkl)
- [training_model_meta.json](/home/dan/Projects/HexeEmail/runtime/providers/gmail/training_model_meta.json)
- sensitivity: moderate
- reason: model artifacts and metadata may reveal training state, labels, or corpus characteristics

## File Permission Behavior

The code currently attempts to protect sensitive files with local file modes:

- `TrustMaterialStore.save()` writes with mode `0600`
- Gmail runtime layout sets `0700` on provider directories and `0600` on:
  - provider config
  - OAuth state secret
  - fetch schedule state
  - quota usage
  - message store when present
  - training model files when present
- `GmailTokenStore.save_token()` sets token files to `0600`

These protections are best-effort:

- they rely on local filesystem support
- chmod failures are ignored in some Gmail runtime helpers when the platform disallows them

## Logging Boundaries

Current logging protections live in [logging_utils.py](/home/dan/Projects/HexeEmail/src/logging_utils.py).

Redacted keys currently include:

- `node_trust_token`
- `operational_mqtt_token`
- `authorization`
- `x-node-trust-token`

Important limitation:

- redaction is key-based, not content-aware
- email bodies, subjects, sender identities, classifier inputs, and ad hoc debug payloads can still be logged if code emits them under non-redacted keys

Operational guidance:

- do not add raw token, mailbox, or message-body payloads to log `event_data`
- treat `runtime/logs/*` as sensitive operational data, especially `providers.log`, `api.log`, and `ai.log`

## Config And Secret Boundaries

### Environment and startup config

From [config.py](/home/dan/Projects/HexeEmail/src/config.py):

- `NODE_NONCE` is required and security-relevant
- `CORE_BASE_URL` and `NODE_NAME` are operational inputs
- `RUNTIME_DIR` controls where sensitive state is written

Implication:

- the runtime directory should not point at a world-readable shared location

### Operator config versus trust config

- [operator_config.json](/home/dan/Projects/HexeEmail/runtime/operator_config.json)
  - operational settings, lower sensitivity
- [trust_material.json](/home/dan/Projects/HexeEmail/runtime/trust_material.json)
  - credential-bearing trust state, high sensitivity

These should not be treated the same in tooling or backups.

## Safe Sharing And Debug Data

Avoid sharing without review:

- `runtime/trust_material.json`
- `runtime/providers/gmail/accounts/*`
- `runtime/providers/gmail/oauth_sessions/*`
- `runtime/providers/gmail/provider_config.json`
- `runtime/providers/gmail/messages.sqlite3`
- `runtime/providers/gmail/reports/*` when they contain classifier inputs or message-derived payloads
- `runtime/order_flow_logs/*` when they include raw HTML or phase outputs derived from real mail

Usually safe to share after review:

- high-level docs under `docs/`
- source code under `src/`
- aggregated benchmark numbers without raw message content

## Current Risk Notes

The current repo already has some protection in place, but the important practical risks are:

- raw Gmail data and derived classifier inputs are stored locally
- generated ORDER logs may contain full HTML and extracted message content
- key-based log redaction does not automatically protect every sensitive field shape
- report/export directories can accumulate user-derived data that is easy to overlook

## Operator Recommendations

- keep `runtime/` out of casual file sharing and screenshots
- back up `runtime/` selectively, not blindly
- treat provider runtime data as private mailbox data
- avoid copying report or log directories into tickets or public issues without review
- review any new debug logging for accidental raw payload disclosure
