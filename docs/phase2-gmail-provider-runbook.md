# Phase 2 Gmail Provider Runbook

## Purpose

This runbook covers Gmail provider activation after the Email Node is already trusted by Core.

Keep the two flows separate:

- Core trust onboarding establishes node trust
- Gmail OAuth authorization links a Gmail provider account to the trusted Email Node

Keep the execution boundary separate too:

- Email Node handles ingress, normalization, routing, provider activation, and automation orchestration
- AI Node handles AI-dependent work when classification or reasoning is needed

## Prerequisites

- the node is already trusted and shows `trust_state=trusted`
- the API is running and reachable
- the operator can reach the local callback endpoint
- Google OAuth credentials are available for the Email Node

## Gmail Config

Populate Gmail provider config under the node runtime using:

- `client_id`
- `client_secret_ref`
- `redirect_uri`
- requested scopes
- provider enabled flag

For local development, the standardized callback reference is:

- `http://localhost:8092/providers/gmail/oauth/callback`

If your current local API runtime is still on `9002`, expose or proxy the callback path there during development until the dedicated callback port convention is adopted in your environment.

The provider config must validate before connect-start will succeed.

## Connect Flow

1. Confirm the node is trusted.
2. Validate Gmail config with `POST /providers/gmail/validate-config`.
3. Start Gmail connect with `POST /providers/gmail/accounts/<account_id>/connect/start`.
4. Open the returned Google connect URL.
5. Complete consent in Google.
6. Let Google redirect back to the Email Node callback endpoint.
7. Confirm the Email Node performs the server-side authorization code exchange.
8. Confirm the callback response returns `status=connected`.

## Post-Connect Expectations

After a successful callback:

- the Gmail token record is stored locally
- the Gmail refresh token is stored locally and securely
- the Gmail account identity is resolved and persisted
- provider state moves to `connected`
- capability declaration is resubmitted with Gmail enabled
- governance is fetched again
- operational readiness can become true once all conditions are satisfied

## Useful Endpoints

- `GET /providers`
- `GET /providers/gmail`
- `GET /providers/gmail/accounts`
- `GET /providers/gmail/accounts/<account_id>`
- `GET /status`
- `GET /health/ready`

## Common Failures

- invalid Gmail config:
  `POST /providers/gmail/validate-config` will report missing fields
- failed token exchange:
  check Google OAuth client, redirect URI, and auth code lifetime
- redirect URI mismatch:
  confirm the Google OAuth Web Application credential includes the callback URI exactly
- missing refresh token:
  reconnect the account and verify offline access is granted
- degraded provider health:
  check granted scopes, refresh-token presence, and identity probe success
- readiness still false:
  confirm trust is still active, capability declaration is accepted, governance sync is `ok`, and Gmail state is `connected`

## Reconnect Or Revocation Recovery

If Gmail access is revoked or the refresh token becomes invalid:

1. inspect `GET /providers/gmail/accounts/<account_id>`
2. start a new Gmail connect flow for that account
3. complete OAuth again
4. confirm the account returns to `connected`

## Capability Notes

The current capability flow is provider-aware:

- supported providers can include Gmail before activation
- enabled providers stay empty until Gmail is healthy and connected
- after Gmail connects, capability declaration is resubmitted with Gmail enabled

## Related Docs

- [email-node-phase2-provider-activation.md](/home/dan/Projects/SynthiaEmail/docs/email-node-phase2-provider-activation.md)
- [gmail-oauth-setup-guide.md](/home/dan/Projects/SynthiaEmail/docs/gmail-oauth-setup-guide.md)
