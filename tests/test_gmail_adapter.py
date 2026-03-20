from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.models import GmailOAuthConfig, GmailTokenRecord
from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.token_client import GmailTokenExchangeClient
from providers.gmail.identity import GmailIdentityProbeClient
from tests.test_gmail_token_client import build_google_token_app


def build_google_identity_app():
    app = FastAPI()

    @app.get("/userinfo")
    async def userinfo():
        return {"id": "google-user-1", "name": "Primary Inbox", "email": "primary@example.com"}

    return app


@pytest.mark.asyncio
async def test_gmail_adapter_reports_configured_connected_account(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret-value")
    GmailProviderConfigStore(tmp_path).save(
        GmailOAuthConfig(
            enabled=True,
            client_id="client-id",
            client_secret_ref="env:GMAIL_CLIENT_SECRET",
        )
    )
    token_client = GmailTokenExchangeClient(transport=ASGITransport(app=build_google_token_app()))
    token_client.TOKEN_ENDPOINT = "http://google.test/token"
    identity_client = GmailIdentityProbeClient(GmailProviderAdapter(tmp_path).account_store, transport=ASGITransport(app=build_google_identity_app()))
    identity_client.USERINFO_ENDPOINT = "http://google.test/userinfo"
    adapter = GmailProviderAdapter(tmp_path, token_client=token_client, identity_client=identity_client)
    await adapter.start_account_connect("primary")
    adapter.account_store.save_account(
        adapter.account_store.load_account("primary")
    )
    await adapter.complete_oauth_callback(
        "primary",
        "auth-code",
        redirect_uri="http://127.0.0.1:8765/oauth2callback",
        code_verifier="verifier",
        correlation_id="corr",
    )

    state = await adapter.get_provider_state()
    accounts = await adapter.list_accounts()
    health = await adapter.get_account_health("primary")
    await adapter.token_client.aclose()
    await adapter.identity_client.aclose()

    assert state == "connected"
    assert accounts[0].status == "connected"
    assert health.status == "connected"
