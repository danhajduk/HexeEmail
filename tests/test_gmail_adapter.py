from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.models import GmailOAuthConfig, GmailStoredMessage, GmailTokenRecord
from providers.gmail.token_client import GmailTokenExchangeClient
from providers.gmail.identity import GmailIdentityProbeClient
from providers.models import ProviderAccountRecord, ProviderId
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
            redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
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
        redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
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


@pytest.mark.asyncio
async def test_gmail_adapter_refresh_mailbox_status_uses_local_message_store(tmp_path):
    GmailProviderConfigStore(tmp_path).save(
        GmailOAuthConfig(
            enabled=True,
            client_id="client-id",
            client_secret_ref="secret",
            redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
        )
    )
    adapter = GmailProviderAdapter(tmp_path)
    adapter.account_store.save_account(
        ProviderAccountRecord(
            provider_id=ProviderId.GMAIL,
            account_id="primary",
            status="connected",
            email_address="primary@example.com",
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-unread-1",
                thread_id="thread-1",
                subject="Unread hello",
                sender="sender@example.com",
                recipients=["primary@example.com"],
                snippet="hello unread world",
                label_ids=["UNREAD", "INBOX"],
                received_at=datetime(2026, 4, 2, 7, 45, 0).astimezone(),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-read-1",
                thread_id="thread-2",
                subject="Read hello",
                sender="reader@example.com",
                recipients=["primary@example.com"],
                snippet="read world",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 2, 6, 45, 0).astimezone(),
            ),
        ],
        now=datetime(2026, 4, 2, 8, 0, 0).astimezone(),
    )

    status = await adapter.refresh_mailbox_status("primary")
    stored_messages = await adapter.list_stored_messages("primary", limit=10)
    summary = await adapter.message_store_summary("primary")
    await adapter.aclose()

    assert status.status == "ok"
    assert status.unread_inbox_count == 1
    assert status.unread_today_count == 1
    assert status.unread_last_hour_count == 1
    assert len(stored_messages) == 2
    assert stored_messages[0].message_id == "msg-unread-1"
    assert summary["total_count"] == 2


@pytest.mark.asyncio
async def test_gmail_adapter_refresh_mailbox_status_works_without_token_when_data_is_local(tmp_path):
    GmailProviderConfigStore(tmp_path).save(
        GmailOAuthConfig(
            enabled=True,
            client_id="client-id",
            client_secret_ref="secret",
            redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
        )
    )
    adapter = GmailProviderAdapter(tmp_path)
    adapter.account_store.save_account(
        ProviderAccountRecord(
            provider_id=ProviderId.GMAIL,
            account_id="primary",
            status="connected",
            email_address="primary@example.com",
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
            account_id="primary",
            message_id="msg-unread-1",
            label_ids=["UNREAD", "INBOX"],
            received_at=datetime(2026, 4, 2, 7, 45, 0).astimezone(),
            )
        ],
        now=datetime(2026, 4, 2, 8, 0, 0).astimezone(),
    )

    status = await adapter.refresh_mailbox_status("primary", store_unread_messages=False)
    stored_messages = await adapter.list_stored_messages("primary", limit=10)
    await adapter.aclose()

    assert status.status == "ok"
    assert status.unread_inbox_count == 1
    assert len(stored_messages) == 1
