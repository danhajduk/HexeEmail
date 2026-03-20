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
- the operator has the helper script available on the workstation that will open the browser
- Google OAuth Desktop app credentials are available for the Email Node

## Gmail Config

Populate Gmail provider config under the node runtime using:

- `client_id`
- `client_secret_ref`
- requested scopes
- provider enabled flag

The fastest operator flow is through the UI on `http://127.0.0.1:8083`:

- open `Setup Provider`
- fill the Gmail fields
- save or validate config
- run the helper command shown in the provider page once the node is trusted

The provider config must validate before connect-start will succeed.

## Connect Flow

1. Confirm the node is trusted.
2. Validate Gmail config with `POST /providers/gmail/validate-config`.
3. Run [`scripts/gmail_desktop_auth.py`](/home/dan/Projects/SynthiaEmail/scripts/gmail_desktop_auth.py) on the operator workstation.
4. The helper asks the node to start Gmail connect with a loopback redirect such as `http://127.0.0.1:8765/oauth2callback`.
5. Open the returned Google connect URL.
6. Complete consent in Google and let the browser return to the workstation loopback listener.
7. Confirm the helper posts the returned `state` and `code` to `POST /providers/gmail/oauth/complete`.
8. Confirm the completion response returns `status=connected`.

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
- `GET /providers/gmail/config`
- `PUT /providers/gmail/config`
- `GET /providers/gmail/accounts`
- `GET /providers/gmail/accounts/<account_id>`
- `POST /providers/gmail/accounts/<account_id>/connect/start`
- `POST /providers/gmail/oauth/complete`
- `GET /status`
- `GET /health/ready`

## Common Failures

- invalid Gmail config:
  `POST /providers/gmail/validate-config` will report missing fields
- failed token exchange:
  check Google OAuth Desktop client, loopback redirect URI, and auth code lifetime
- loopback redirect problems:
  confirm the helper is using `127.0.0.1` or `localhost` and the workstation firewall allows local listener startup
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
