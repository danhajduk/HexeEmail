# Gmail OAuth Setup Guide

## Purpose

This guide covers Gmail authentication for the Email Node using:

- Google OAuth 2.0
- Desktop app client credentials
- operator-workstation loopback redirect
- server-side Authorization Code flow with PKCE

Keep this separate from Core trust onboarding:

- Core trust onboarding establishes whether the Email Node is trusted by Synthia Core
- Gmail provider authorization grants the trusted Email Node access to a Gmail provider account

## OAuth Model

The Email Node Gmail flow uses:

- Google OAuth client type: `Desktop app`
- authorization code returned to a loopback listener on the operator workstation
- server-side token exchange in the Email Node with PKCE
- local refresh-token storage in the Email Node runtime

## Google Cloud Setup

1. Create or select a Google Cloud project.
2. Enable the Gmail API for that project.
3. Configure the OAuth consent screen in Google Auth Platform.
4. Create OAuth credentials.
5. Choose application type:
   `Desktop app`

## Credential Fields

- Client ID:
  public identifier used by Google to identify the Email Node OAuth client
- Client Secret:
  optional secret reference used by the Email Node during server-side token exchange when present
- Loopback Redirect URI:
  temporary local callback the helper opens on the operator workstation
- Authorization Code:
  short-lived code returned to the helper loopback listener
- Access Token:
  short-lived token used for Gmail API calls
- Refresh Token:
  long-lived token stored locally so the Email Node can refresh access later

## Email Node Config

Configure the Gmail provider with:

- Gmail client id
- Gmail client secret source or reference
- requested Gmail scopes
- provider enabled flag

Current implementation examples:

- `client_id`
- `client_secret_ref=env:GMAIL_CLIENT_SECRET`

## Flow Summary

1. Core trust onboarding completes first.
2. The trusted Email Node validates Gmail config.
3. The operator runs the desktop helper on the workstation that will open the browser.
4. The helper starts a loopback listener and asks the Email Node to generate a Google connect URL for that redirect.
5. The operator opens the URL and grants consent.
6. Google redirects to the workstation loopback listener.
7. The helper posts the returned `state` and `code` back to the Email Node.
8. The Email Node exchanges the authorization code server-side and stores the refresh token locally and securely.
9. The Email Node probes Gmail identity and marks the account connected.

## Common Errors

### Loopback Redirect Problems

- confirm the helper is using `127.0.0.1` or `localhost`
- confirm the local port is free on the workstation
- confirm firewall rules are not blocking the local listener

### `invalid_client`

- verify the Client ID and Client Secret belong to the same Desktop app credential
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
- OAuth Desktop app client created
- helper starts local callback listener successfully
- successful helper completion received
- refresh token stored
- Gmail account marked connected

## Related Docs

- [email-node-phase2-provider-activation.md](/home/dan/Projects/SynthiaEmail/docs/email-node-phase2-provider-activation.md)
- [phase2-gmail-provider-runbook.md](/home/dan/Projects/SynthiaEmail/docs/phase2-gmail-provider-runbook.md)
