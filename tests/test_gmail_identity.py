from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport
import pytest

from providers.gmail.account_store import GmailAccountStore
from providers.gmail.identity import GmailIdentityProbeClient, GmailIdentityProbeError
from providers.gmail.models import GmailTokenRecord


def build_google_identity_app(include_email: bool = True):
    app = FastAPI()

    @app.get("/userinfo")
    async def userinfo():
        payload = {"id": "google-user-1", "name": "Primary Inbox"}
        if include_email:
            payload["email"] = "primary@example.com"
        return payload

    return app


@pytest.mark.asyncio
async def test_gmail_identity_probe_persists_provider_account_record(tmp_path):
    account_store = GmailAccountStore(tmp_path)
    client = GmailIdentityProbeClient(account_store, transport=ASGITransport(app=build_google_identity_app()))
    client.USERINFO_ENDPOINT = "http://google.test/userinfo"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    record = await client.probe_identity(token, correlation_id="corr-123")
    saved = account_store.load_account("primary")
    await client.aclose()

    assert record.email_address == "primary@example.com"
    assert saved is not None
    assert saved.external_account_id == "google-user-1"
    assert saved.status == "token_exchanged"


@pytest.mark.asyncio
async def test_gmail_identity_probe_requires_email_address(tmp_path):
    account_store = GmailAccountStore(tmp_path)
    client = GmailIdentityProbeClient(account_store, transport=ASGITransport(app=build_google_identity_app(False)))
    client.USERINFO_ENDPOINT = "http://google.test/userinfo"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    with pytest.raises(GmailIdentityProbeError):
        await client.probe_identity(token)

    await client.aclose()
