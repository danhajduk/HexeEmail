# Gmail OAuth Setup Guide

## Purpose

This guide covers Gmail authentication for the Email Node using:

- Google OAuth 2.0
- Web application client credentials
- public HTTPS callback on the Email Node, typically through Cloudflare Tunnel
- server-side Authorization Code flow

Keep this separate from Core trust onboarding:

- Core trust onboarding establishes whether the Email Node is trusted by Hexe Core
- Gmail provider authorization grants the trusted Email Node access to a Gmail provider account

## OAuth Model

The Email Node Gmail flow uses:

- Google OAuth client type: `Web application`
- authorization code returned to the Email Node callback endpoint
- server-side token exchange in the Email Node
- local refresh-token storage in the Email Node runtime

## Google Cloud Setup

1. Create or select a Google Cloud project.
2. Enable the Gmail API for that project.
3. Configure the OAuth consent screen in Google Auth Platform.
4. Create OAuth credentials.
5. Choose application type:
   `Web application`
6. Add the authorized redirect URI:
   `https://email-node.example.com/providers/gmail/oauth/callback`

## Credential Fields

- Client ID:
  public identifier used by Google to identify the Email Node OAuth client
- Client Secret:
  secret used by the Email Node during server-side token exchange
- Redirect URI:
  public HTTPS callback endpoint Google redirects to after consent
- Authorization Code:
  short-lived code returned to the Email Node callback
- Access Token:
  short-lived token used for Gmail API calls
- Refresh Token:
  long-lived token stored locally so the Email Node can refresh access later

## Email Node Config

Configure the Gmail provider with:

- Gmail client id
- Gmail client secret source or reference
- Gmail redirect URI
- requested Gmail scopes
- provider enabled flag

Current implementation examples:

- `client_id`
- `client_secret_ref=env:GMAIL_CLIENT_SECRET`
- `redirect_uri=https://email-node.example.com/providers/gmail/oauth/callback`

## Flow Summary

1. Core trust onboarding completes first.
2. The trusted Email Node validates Gmail config.
3. The Email Node generates a Google connect URL.
4. The operator opens the URL and grants consent.
5. Google redirects to the Email Node callback through the public HTTPS hostname.
6. The Email Node exchanges the authorization code server-side and stores the refresh token locally and securely.
7. The Email Node probes Gmail identity and marks the account connected.

## Common Errors

### `redirect_uri_mismatch`

- confirm the callback URI in Google exactly matches the URI the Email Node uses
- if using Cloudflare Tunnel, confirm the public hostname and path match exactly

### `invalid_client`

- verify the Client ID and Client Secret belong to the same Web application credential
- confirm the Email Node is reading the correct secret source

### `invalid_grant`

- the authorization code may be expired or already used
- the refresh token may be revoked or invalid
- restart the connect flow and complete consent again

### Missing Refresh Token

- verify offline access is requested
- verify the Google account actually granted long-lived access
- revoke and reconnect if needed

### Consent Or Scope Mismatch

- confirm the requested Gmail scopes match the intended capability
- update the OAuth consent configuration if Google blocks the requested scope set

## Secure Handling Rules

- do not commit Client Secrets
- do not expose refresh tokens in logs
- store OAuth tokens only in Email Node runtime secret storage
- keep Core trust credentials separate from Gmail provider credentials

## Verification Checklist

- Gmail API enabled
- OAuth Web application client created
- redirect URI registered correctly
- successful OAuth callback received
- refresh token stored
- Gmail account marked connected

## Related Docs

- [email-node-phase2-provider-activation.md](email-node-phase2-provider-activation.md)
- [phase2-gmail-provider-runbook.md](phase2-gmail-provider-runbook.md)
