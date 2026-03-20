# Phase 2 Manual Acceptance

## Goal

Validate the trusted Email Node plus Gmail provider activation flow end to end.

This acceptance path should confirm:

- Core trust onboarding is already complete
- Gmail authorization happens through Google OAuth Web application flow
- Email Node handles ingress/provider activation
- AI work remains delegated to AI Node

## Preconditions

- Core onboarding is already complete
- the node is trusted
- Gmail OAuth config is present and valid
- the node is reachable through a public HTTPS callback, typically via Cloudflare Tunnel

## Acceptance Steps

1. Start the node API.
2. Confirm `GET /status` shows `trust_state=trusted`.
3. Confirm `GET /providers/gmail` shows the provider is configured.
4. Call `POST /providers/gmail/validate-config` and confirm validation succeeds.
5. Start Gmail connect:
   `POST /providers/gmail/accounts/primary/connect/start`
6. Open the returned Google OAuth URL.
7. Complete Google consent.
8. Confirm Google redirects to the Email Node callback endpoint through the public HTTPS hostname and the callback succeeds at:
   `https://email-node.example.com/providers/gmail/oauth/callback?...`
9. Confirm `GET /providers/gmail/accounts/primary` reports connected health.
10. Confirm `GET /providers` lists:
   - `supported_providers` includes `gmail`
   - `enabled_providers` includes `gmail`
11. Confirm `GET /status` reports:
   - capability declaration accepted
   - governance sync status `ok`
   - operational readiness `true`
12. Confirm `GET /health/ready` returns `ready=true`.

## Expected Results

- Gmail token stored securely
- Gmail account identity persisted
- Gmail provider state connected
- normalized email ingress/provider path ready
- capability declaration updated after activation
- governance fetched successfully
- node operational readiness true
- AI delegation boundary remains explicit in the architecture and runbook

## Failure Notes

If acceptance fails, capture:

- provider validation output
- provider account status output
- `/status`
- `/health/ready`
- relevant structured logs for token exchange, identity probe, capability declaration, and governance sync
