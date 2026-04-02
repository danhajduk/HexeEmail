from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.models import GmailOAuthConfig, GmailSpamhausCheck, GmailStoredMessage, GmailTokenRecord
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


@pytest.mark.asyncio
async def test_gmail_adapter_fetch_window_saves_each_page_incrementally(tmp_path):
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
    adapter.token_store.save_token(
        "primary",
        GmailTokenRecord(
            account_id="primary",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
        ),
    )

    class IncrementalMailboxClient:
        quota_tracker = None

        def build_fetch_query(self, window: str, *, now=None) -> str:
            return f"query:{window}"

        async def iter_message_batches(self, *, token_record, query):
            yield [
                GmailStoredMessage(
                    account_id="primary",
                    message_id="msg-1",
                    sender="sender1@example.com",
                    received_at=datetime(2026, 4, 2, 8, 0, 0).astimezone(),
                )
            ]
            assert adapter.message_store.count_messages("primary") == 1
            yield [
                GmailStoredMessage(
                    account_id="primary",
                    message_id="msg-2",
                    sender="sender2@example.com",
                    received_at=datetime(2026, 4, 2, 9, 0, 0).astimezone(),
                )
            ]

    adapter.mailbox_client = IncrementalMailboxClient()

    result = await adapter.fetch_messages_for_window("primary", window="today")

    assert result["fetched_count"] == 2
    assert result["stored_count"] == 2
    assert adapter.message_store.count_messages("primary") == 2


@pytest.mark.asyncio
async def test_gmail_adapter_does_not_recheck_messages_already_sent_to_spamhaus(tmp_path):
    GmailProviderConfigStore(tmp_path).save(
        GmailOAuthConfig(
            enabled=True,
            client_id="client-id",
            client_secret_ref="secret",
            redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
        )
    )
    adapter = GmailProviderAdapter(tmp_path)
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Sender <sender@example.com>",
                received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
            )
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )

    class CountingSpamhausChecker:
        def __init__(self) -> None:
            self.calls = 0

        async def check_sender(self, *, account_id: str, message_id: str, sender: str | None):
            self.calls += 1
            return GmailSpamhausCheck(
                account_id=account_id,
                message_id=message_id,
                sender_email="sender@example.com",
                sender_domain="example.com",
                checked=True,
                listed=False,
                status="clean",
                detail="clean in test",
            )

    checker = CountingSpamhausChecker()
    adapter.spamhaus_checker = checker

    first = await adapter.check_spamhaus_for_stored_messages("primary")
    second = await adapter.check_spamhaus_for_stored_messages("primary")

    assert checker.calls == 1
    assert first["checked_count"] == 1
    assert second["checked_count"] == 0
    assert first["summary"]["checked_count"] == 1
    assert second["summary"]["checked_count"] == 1


@pytest.mark.asyncio
async def test_gmail_adapter_initial_learning_fetch_does_not_require_schedule_slot(tmp_path):
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
    adapter.token_store.save_token(
        "primary",
        GmailTokenRecord(
            account_id="primary",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
        ),
    )

    class InitialLearningMailboxClient:
        quota_tracker = None

        def build_fetch_query(self, window: str, *, now=None) -> str:
            return f"query:{window}"

        async def iter_message_batches(self, *, token_record, query):
            yield [
                GmailStoredMessage(
                    account_id="primary",
                    message_id="msg-1",
                    sender="sender@example.com",
                    received_at=datetime(2026, 4, 2, 8, 0, 0).astimezone(),
                )
            ]

    adapter.mailbox_client = InitialLearningMailboxClient()

    result = await adapter.fetch_messages_for_window("primary", window="initial_learning")

    assert result["window"] == "initial_learning"
    assert result["stored_count"] == 1
