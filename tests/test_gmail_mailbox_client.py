from __future__ import annotations

from datetime import datetime
import base64

from fastapi import FastAPI, Query
from httpx import ASGITransport
import pytest

from providers.gmail.mailbox_client import GmailMailboxClient
from providers.gmail.models import GmailTokenRecord


def build_google_mailbox_app():
    app = FastAPI()
    counters = iter([3, 4, 2])

    @app.get("/messages")
    async def messages(q: str = Query(default="")):
        if q == "is:unread in:inbox":
            return {"resultSizeEstimate": 11}
        if q.startswith("is:unread after:"):
            return {"resultSizeEstimate": next(counters)}
        return {"resultSizeEstimate": 0}

    return app


@pytest.mark.asyncio
async def test_gmail_mailbox_client_fetches_unread_counts():
    client = GmailMailboxClient(transport=ASGITransport(app=build_google_mailbox_app()))
    client.MESSAGES_ENDPOINT = "http://google.test/messages"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    status = await client.fetch_unread_status(token_record=token, email_address="primary@example.com")
    await client.aclose()

    assert status.account_id == "primary"
    assert status.email_address == "primary@example.com"
    assert status.status == "ok"
    assert status.unread_inbox_count == 11
    assert status.unread_today_count == 3
    assert status.unread_yesterday_count == 4
    assert status.unread_last_hour_count == 2


@pytest.mark.asyncio
async def test_gmail_mailbox_client_fetches_unread_messages():
    client = GmailMailboxClient(transport=ASGITransport(app=build_google_fetch_app()))
    client.MESSAGES_ENDPOINT = "http://google.test/messages"
    client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    messages = await client.fetch_unread_messages(token_record=token)
    await client.aclose()

    assert len(messages) == 1
    assert messages[0].message_id == "msg-1"
    assert messages[0].subject == "Hello"


def build_google_fetch_app():
    app = FastAPI()

    @app.get("/messages")
    async def list_messages(q: str = Query(default=""), pageToken: str | None = None):
        if pageToken:
            return {"messages": []}
        assert q == "is:unread" or q.startswith("after:")
        return {"messages": [{"id": "msg-1"}]}

    @app.get("/messages/{message_id}")
    async def get_message(message_id: str):
        assert message_id == "msg-1"
        return {
            "id": "msg-1",
            "threadId": "thread-1",
            "labelIds": ["INBOX"],
            "snippet": "hello world",
            "internalDate": "1775121600000",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Sender <sender@example.com>"},
                    {"name": "To", "value": "primary@example.com"},
                    {"name": "Subject", "value": "Hello"},
                ]
            },
        }

    return app


@pytest.mark.asyncio
async def test_gmail_mailbox_client_fetches_message_metadata():
    client = GmailMailboxClient(transport=ASGITransport(app=build_google_fetch_app()))
    client.MESSAGES_ENDPOINT = "http://google.test/messages"
    client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    messages = await client.fetch_messages(token_record=token, query="in:inbox after:1 before:2")
    await client.aclose()

    assert len(messages) == 1
    assert messages[0].message_id == "msg-1"
    assert messages[0].thread_id == "thread-1"
    assert messages[0].subject == "Hello"
    assert messages[0].sender == "Sender <sender@example.com>"
    assert messages[0].recipients == ["primary@example.com"]


@pytest.mark.asyncio
async def test_gmail_mailbox_client_fetches_full_message_text_from_plain_part():
    app = FastAPI()
    encoded_text = base64.urlsafe_b64encode(b"Hello Dan,\nYour order ships tomorrow.\n").decode("ascii").rstrip("=")

    @app.get("/messages/msg-1")
    async def get_message():
        return {
            "id": "msg-1",
            "threadId": "thread-1",
            "snippet": "Your order ships tomorrow.",
            "payload": {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": encoded_text,
                        },
                    }
                ],
            },
        }

    client = GmailMailboxClient(transport=ASGITransport(app=app))
    client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    full_message = await client.fetch_full_message_text(token_record=token, message_id="msg-1")
    await client.aclose()

    assert full_message["message_id"] == "msg-1"
    assert full_message["text_body"] == "Hello Dan,\nYour order ships tomorrow."
    assert full_message["html_body"] == ""


@pytest.mark.asyncio
async def test_gmail_mailbox_client_fetch_full_message_keeps_html_body():
    app = FastAPI()
    encoded_html = "PGRpdj48cD5IZWxsbyBEYW4sPC9wPjxwPllvdXIgb3JkZXIgPHN0cm9uZz5zaGlwczwvc3Ryb25nPiB0b21vcnJvdy48L3A+PC9kaXY+"

    @app.get("/messages/{message_id}")
    async def message(message_id: str):
        return {
            "id": message_id,
            "threadId": "thread-1",
            "snippet": "Your order ships tomorrow.",
            "payload": {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {
                            "data": encoded_html,
                        },
                    }
                ],
            },
        }

    client = GmailMailboxClient(transport=ASGITransport(app=app))
    client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    full_message = await client.fetch_full_message_text(token_record=token, message_id="msg-1")
    await client.aclose()

    assert full_message["text_body"] == "Hello Dan,\nYour order ships tomorrow."
    assert full_message["html_body"] == "<div><p>Hello Dan,</p><p>Your order <strong>ships</strong> tomorrow.</p></div>"


@pytest.mark.asyncio
async def test_gmail_mailbox_client_fetches_labels():
    app = FastAPI()

    @app.get("/labels")
    async def labels():
        return {
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "Label_74", "name": "Hexe/Scanned", "type": "user"},
            ]
        }

    client = GmailMailboxClient(transport=ASGITransport(app=app))
    client.LABELS_ENDPOINT = "http://google.test/labels"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    labels = await client.fetch_labels(token_record=token)
    await client.aclose()

    assert labels == [
        {
            "id": "INBOX",
            "name": "INBOX",
            "type": "system",
            "message_list_visibility": None,
            "label_list_visibility": None,
        }
    ]


def test_gmail_mailbox_client_builds_local_time_window_queries():
    client = GmailMailboxClient()
    now = datetime(2026, 4, 2, 15, 30, 0).astimezone()

    today_query = client.build_fetch_query("today", now=now)
    yesterday_query = client.build_fetch_query("yesterday", now=now)
    last_hour_query = client.build_fetch_query("last_hour", now=now)
    initial_query = client.build_fetch_query("initial_learning", now=now)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    next_second = now + timedelta(seconds=1)
    initial_start = now.replace(year=2025, month=10, day=2)

    assert today_query == f"after:{int(today_start.timestamp())} before:{int(next_second.timestamp())}"
    assert yesterday_query == f"after:{int(yesterday_start.timestamp())} before:{int(today_start.timestamp())}"
    assert last_hour_query == f"after:{int((now - timedelta(hours=1)).timestamp())} before:{int(next_second.timestamp())}"
    assert initial_query == f"after:{int(initial_start.timestamp())} before:{int(next_second.timestamp())}"
    assert "in:inbox" not in today_query
    assert "in:inbox" not in yesterday_query
    assert "in:inbox" not in last_hour_query
    assert "in:inbox" not in initial_query


@pytest.mark.asyncio
async def test_gmail_mailbox_client_slows_down_when_quota_usage_crosses_90_percent(monkeypatch):
    client = GmailMailboxClient(transport=ASGITransport(app=build_google_fetch_app()))
    client.MESSAGES_ENDPOINT = "http://google.test/messages"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")
    sleep_calls: list[float] = []

    class SlowdownQuotaTracker:
        def snapshot(self, account_id: str):
            return type(
                "Snapshot",
                (),
                {"used_last_minute": 13500, "limit_per_minute": 15000},
            )()

        def seconds_until_available(self, account_id: str, units: int):
            return 0.0

        def reserve(self, account_id: str, units: int, operation: str):
            return None

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    client.quota_tracker = SlowdownQuotaTracker()
    monkeypatch.setattr("providers.gmail.mailbox_client.asyncio.sleep", fake_sleep)

    await client.fetch_messages(token_record=token, query="in:inbox after:1 before:2")
    await client.aclose()

    assert sleep_calls == [client.QUOTA_SLOWDOWN_DELAY_SECONDS, client.QUOTA_SLOWDOWN_DELAY_SECONDS]


@pytest.mark.asyncio
async def test_gmail_mailbox_client_pauses_when_quota_usage_crosses_99_percent(monkeypatch):
    client = GmailMailboxClient(transport=ASGITransport(app=build_google_fetch_app()))
    client.MESSAGES_ENDPOINT = "http://google.test/messages"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")
    sleep_calls: list[float] = []

    class PauseQuotaTracker:
        def snapshot(self, account_id: str):
            return type(
                "Snapshot",
                (),
                {"used_last_minute": 14900, "limit_per_minute": 15000},
            )()

        def seconds_until_available(self, account_id: str, units: int):
            return 12.0

        def reserve(self, account_id: str, units: int, operation: str):
            return None

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    client.quota_tracker = PauseQuotaTracker()
    monkeypatch.setattr("providers.gmail.mailbox_client.asyncio.sleep", fake_sleep)

    await client.fetch_messages(token_record=token, query="in:inbox after:1 before:2")
    await client.aclose()

    assert sleep_calls == [12.0, 12.0]
