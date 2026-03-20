from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport
import pytest

from providers.gmail.models import GmailOAuthConfig
from providers.gmail.token_client import GmailTokenExchangeClient, GmailTokenExchangeError


def build_google_token_app(success: bool = True):
    app = FastAPI()

    @app.post("/token")
    async def token():
        if success:
            return {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/gmail.send",
            }
        return {
            "error": "invalid_grant",
            "error_description": "authorization code expired",
        }

    return app


@pytest.mark.asyncio
async def test_gmail_token_client_normalizes_google_token_response(monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret-value")
    client = GmailTokenExchangeClient(transport=ASGITransport(app=build_google_token_app()))
    client.TOKEN_ENDPOINT = "http://google.test/token"
    oauth_config = GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="http://127.0.0.1:9002/providers/gmail/oauth/callback",
    )

    token = await client.exchange_authorization_code(oauth_config, account_id="primary", code="auth-code")
    await client.aclose()

    assert token.account_id == "primary"
    assert token.access_token == "access-token"
    assert token.refresh_token == "refresh-token"
    assert token.granted_scopes == ["https://www.googleapis.com/auth/gmail.send"]
    assert token.expires_at is not None


@pytest.mark.asyncio
async def test_gmail_token_client_surfaces_invalid_grant(monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret-value")
    client = GmailTokenExchangeClient(transport=ASGITransport(app=build_google_token_app(success=False)))
    client.TOKEN_ENDPOINT = "http://google.test/token"
    oauth_config = GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="http://127.0.0.1:9002/providers/gmail/oauth/callback",
    )

    with pytest.raises(GmailTokenExchangeError):
        await client.exchange_authorization_code(oauth_config, account_id="primary", code="bad-code")

    await client.aclose()
