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
- Core can receive the centralized public Gmail callback and forward it to the node callback endpoint
- Google OAuth Web application credentials are available for the Email Node

## Gmail Config

Populate Gmail provider config under the node runtime using:

- `client_id`
- `client_secret_ref`
- `redirect_uri`
- requested scopes
- provider enabled flag

The fastest operator flow is through the UI on `http://127.0.0.1:8083`:

- open `Setup Provider`
- fill the Gmail fields
- save or validate config
- start the connect flow once the node is trusted

The provider config must validate before connect-start will succeed.

## Connect Flow

1. Confirm the node is trusted.
2. Validate Gmail config with `POST /providers/gmail/validate-config`.
3. Set `redirect_uri` to the centralized public callback:
   `https://hexe-ai.com/google/gmail/callback`
4. Set the requested scopes to:
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/gmail.readonly`
5. Start Gmail connect with `POST /providers/gmail/accounts/<account_id>/connect/start`.
6. Open the returned Google connect URL.
7. Complete consent in Google and let the browser return through the centralized callback and forwarded node callback endpoint.
8. Confirm the Email Node performs the server-side authorization code exchange.
9. Confirm the callback response returns `status=connected`.

## Post-Connect Expectations

After a successful callback:

- the Gmail token record is stored locally
- the Gmail refresh token is stored locally and securely
- the Gmail account identity is resolved and persisted
- provider state moves to `connected`
- capability declaration is resubmitted with Gmail enabled
- governance is fetched again
- operational readiness can become true once all conditions are satisfied

## Gmail Fetch And Local Store

Once Gmail is connected, the dashboard Gmail section exposes manual fetch actions for:

- initial learning
- today
- yesterday
- last hour

These actions call the local node API:

- `POST /api/gmail/fetch/initial_learning`
- `POST /api/gmail/fetch/today`
- `POST /api/gmail/fetch/yesterday`
- `POST /api/gmail/fetch/last_hour`

Fetched message metadata is stored locally in SQLite at:

- `runtime/providers/gmail/messages.sqlite3`

Retention policy:

- the node keeps up to the most recent six months of fetched Gmail messages
- records older than six months are pruned during store updates

Current unread counter behavior:

- `Unread Inbox` is limited to `is:unread in:inbox`
- `Unread Today`, `Unread Yesterday`, and `Unread This Week` count unread mail by time window across Gmail and are not restricted to inbox only
- counts are based on exact Gmail message matches instead of `resultSizeEstimate`

## Useful Endpoints

- `GET /providers`
- `GET /providers/gmail`
- `GET /providers/gmail/config`
- `PUT /providers/gmail/config`
- `GET /providers/gmail/accounts`
- `GET /providers/gmail/accounts/<account_id>`
- `GET /api/gmail/status`
- `POST /api/gmail/fetch/initial_learning`
- `POST /api/gmail/fetch/today`
- `POST /api/gmail/fetch/yesterday`
- `POST /api/gmail/fetch/last_hour`
- `POST /providers/gmail/accounts/<account_id>/connect/start`
- `GET /google/gmail/callback`
- `GET /status`
- `GET /health/ready`

## Common Failures

- invalid Gmail config:
  `POST /providers/gmail/validate-config` will report missing fields
- failed token exchange:
  check Google OAuth Web application client, redirect URI, and auth code lifetime
- invalid client secret:
  confirm the saved `client_secret_ref` belongs to the same Google OAuth client as `client_id`
- redirect URI mismatch:
  confirm the Google OAuth Web application credential includes `https://hexe-ai.com/google/gmail/callback` exactly
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

- [email-node-phase2-provider-activation.md](email-node-phase2-provider-activation.md)
- [gmail-oauth-setup-guide.md](gmail-oauth-setup-guide.md)
