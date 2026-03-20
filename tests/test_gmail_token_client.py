from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport
import pytest

from providers.gmail.account_store import GmailAccountStore
from providers.gmail.models import GmailOAuthConfig, GmailTokenRecord
from providers.gmail.token_client import GmailTokenExchangeClient, GmailTokenExchangeError
from providers.gmail.token_store import GmailTokenStore
from providers.models import ProviderAccountRecord, ProviderId


def build_google_token_app(success: bool = True, *, refresh: bool = False):
    app = FastAPI()

    @app.post("/token")
    async def token():
        if success:
            if refresh:
                return {
                    "access_token": "refreshed-access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/gmail.send",
                }
            return {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/gmail.send",
            }
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_grant",
                "error_description": "authorization code expired",
            },
        )

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
        redirect_uri="https://email-node.example.com/providers/gmail/oauth/callback",
    )

    token = await client.exchange_authorization_code(
        oauth_config,
        account_id="primary",
        code="auth-code",
        redirect_uri="https://email-node.example.com/providers/gmail/oauth/callback",
        code_verifier="verifier",
    )
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
        redirect_uri="https://email-node.example.com/providers/gmail/oauth/callback",
    )

    with pytest.raises(GmailTokenExchangeError):
        await client.exchange_authorization_code(
            oauth_config,
            account_id="primary",
            code="bad-code",
            redirect_uri="https://email-node.example.com/providers/gmail/oauth/callback",
            code_verifier="verifier",
        )

    await client.aclose()


@pytest.mark.asyncio
async def test_gmail_token_client_refreshes_and_persists_near_expiry_token(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret-value")
    client = GmailTokenExchangeClient(transport=ASGITransport(app=build_google_token_app(refresh=True)))
    client.TOKEN_ENDPOINT = "http://google.test/token"
    oauth_config = GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="https://email-node.example.com/providers/gmail/oauth/callback",
    )
    token_store = GmailTokenStore(tmp_path)
    account_store = GmailAccountStore(tmp_path)
    token_store.save_token(
        "primary",
        GmailTokenRecord(
            account_id="primary",
            access_token="expiring-access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=30),
            granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
        ),
    )
    account_store.save_account(
        ProviderAccountRecord(provider_id=ProviderId.GMAIL, account_id="primary", status="token_exchanged")
    )

    refreshed = await client.refresh_if_needed(
        oauth_config,
        account_id="primary",
        token_store=token_store,
        account_store=account_store,
    )
    await client.aclose()

    assert refreshed is not None
    assert refreshed.access_token == "refreshed-access-token"
    assert token_store.load_token("primary").access_token == "refreshed-access-token"


@pytest.mark.asyncio
async def test_gmail_token_client_marks_account_revoked_on_invalid_refresh(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret-value")
    client = GmailTokenExchangeClient(transport=ASGITransport(app=build_google_token_app(success=False, refresh=True)))
    client.TOKEN_ENDPOINT = "http://google.test/token"
    oauth_config = GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="https://email-node.example.com/providers/gmail/oauth/callback",
    )
    token_store = GmailTokenStore(tmp_path)
    account_store = GmailAccountStore(tmp_path)
    token_store.save_token(
        "primary",
        GmailTokenRecord(
            account_id="primary",
            access_token="expiring-access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=30),
        ),
    )
    account_store.save_account(
        ProviderAccountRecord(provider_id=ProviderId.GMAIL, account_id="primary", status="connected")
    )

    with pytest.raises(GmailTokenExchangeError):
        await client.refresh_if_needed(
            oauth_config,
            account_id="primary",
            token_store=token_store,
            account_store=account_store,
        )

    account = account_store.load_account("primary")
    await client.aclose()

    assert account is not None
    assert account.status == "revoked"
