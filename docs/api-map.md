# API Map

This document maps the current API surface by canonical Hexe node groups.

Primary evidence source:

- [src/main.py](/home/dan/Projects/HexeEmail/src/main.py)

## Health

Canonical:

- `GET /api/health`
- `GET /health/live`
- `GET /health/ready`

Notes:

- `/api/health` is the main API health route
- `/health/live` and `/health/ready` remain acceptable node-health routes

## Node

Canonical:

- `GET /api/node/status`
- `GET /api/node/bootstrap`
- `GET /api/node/config`
- `PUT /api/node/config`
- `POST /api/node/recover`

Compatibility:

- `GET /status`
- `GET /ui/bootstrap`
- `GET /ui/config`
- `PUT /ui/config`

## Onboarding

Canonical:

- `POST /api/onboarding/start`

Compatibility:

- `GET /onboarding/status`
- `POST /ui/onboarding/start`
- `POST /ui/onboarding/restart`

Notes:

- bare `/onboarding/status` is a compatibility route and should be treated as non-canonical

## Capabilities

Canonical:

- `POST /api/capabilities/declare`
- `GET /api/capabilities/config`
- `POST /api/capabilities/config`
- `GET /api/capabilities/diagnostics`
- `GET /api/capabilities/node/resolved`
- `POST /api/capabilities/redeclare`
- `POST /api/capabilities/rebuild`

Compatibility:

- `POST /ui/capabilities/declare`

## Governance

Canonical:

- `GET /api/governance/status`
- `POST /api/governance/refresh`

## Runtime

Canonical:

- `POST /api/tasks/routing/preview`
- `POST /api/runtime/execute-authorized-task`
- `POST /api/runtime/prompts/sync`
- `POST /api/runtime/settings`
- `POST /api/runtime/execute-email-classifier`
- `POST /api/runtime/execute-email-classifier-batch`
- `POST /api/runtime/execute-latest-email-action-decision`

Compatibility or transitional:

- `POST /api/core/services/resolve`
- `POST /api/core/services/authorize`

Notes:

- these two routes are still API-facing and useful, but they are Core-routing compatibility/domain-crossing routes rather than clean node-runtime ownership paths

## Services

Canonical:

- `GET /api/services/status`
- `POST /api/services/restart`

## Providers

Canonical target ownership:

- `/api/providers`
- `/api/providers/gmail/*`

Current compatibility or non-canonical routes:

- `GET /providers`
- `GET /providers/gmail`
- `GET /providers/gmail/config`
- `PUT /providers/gmail/config`
- `GET /providers/gmail/accounts`
- `GET /providers/gmail/accounts/{account_id}`
- `POST /providers/gmail/validate-config`
- `POST /providers/gmail/accounts/{account_id}/connect/start`

Notes:

- the repo already implements provider functionality, but the provider ownership path still mixes bare `/providers/*` routes with `/api/gmail/*` routes

## Gmail-specific routes

Current implemented Gmail API routes:

- `GET /api/gmail/status`
- `POST /api/gmail/fetch/{window}`
- `POST /api/gmail/spamhaus/check`
- `POST /api/gmail/reputation/refresh`
- `GET /api/gmail/training`
- `GET /api/gmail/reputation`
- `GET /api/gmail/reputation/detail`
- `POST /api/gmail/reputation/manual-rating`
- `POST /api/gmail/training/manual-batch`
- `POST /api/gmail/training/manual-classify`
- `POST /api/gmail/training/train-model`
- `POST /api/gmail/training/semi-auto-batch`
- `POST /api/gmail/training/classified-batch`
- `POST /api/gmail/training/semi-auto-review`

## Callback and compatibility endpoints

Compatibility or domain-specific routes:

- `GET /google/callback`

Notes:

- this is not a canonical node API route group; it is a provider OAuth callback compatibility path

## Standards summary

Current status:

- many canonical `/api/*` route groups already exist
- compatibility aliases are still mixed into the main app surface
- provider ownership still needs normalization toward `/api/providers` and `/api/providers/gmail/*`
- route registration is still monolithic in [src/main.py](/home/dan/Projects/HexeEmail/src/main.py)
