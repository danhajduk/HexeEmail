from __future__ import annotations

from datetime import datetime

from providers.gmail.message_store import GmailMessageStore
from providers.gmail.models import GmailStoredMessage


def test_gmail_message_store_persists_messages(runtime_dir):
    store = GmailMessageStore(runtime_dir)

    inserted = store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                thread_id="thread-1",
                subject="Hello",
                sender="sender@example.com",
                recipients=["primary@example.com"],
                snippet="hello world",
                label_ids=["INBOX", "UNREAD"],
                received_at=datetime(2026, 4, 1, 12, 0, 0),
            )
        ],
        now=datetime(2026, 4, 2, 12, 0, 0),
    )

    assert inserted == 1
    assert store.count_messages("primary") == 1
    saved = store.list_messages("primary", limit=1)[0]
    assert saved.message_id == "msg-1"
    assert saved.subject == "Hello"
    assert saved.recipients == ["primary@example.com"]


def test_gmail_message_store_enforces_six_month_retention(runtime_dir):
    store = GmailMessageStore(runtime_dir)

    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="old-msg",
                received_at=datetime(2025, 9, 30, 8, 0, 0),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="fresh-msg",
                received_at=datetime(2026, 3, 31, 8, 0, 0),
            ),
        ],
        now=datetime(2026, 4, 2, 12, 0, 0),
    )

    messages = store.list_messages("primary", limit=10)
    assert [message.message_id for message in messages] == ["fresh-msg"]
