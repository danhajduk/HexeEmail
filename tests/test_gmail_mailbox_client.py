from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Query
from httpx import ASGITransport
import pytest

from providers.gmail.mailbox_client import GmailMailboxClient
from providers.gmail.models import GmailTokenRecord


def build_google_mailbox_app():
    app = FastAPI()
    responses = {
        "is:unread in:inbox": [{"messages": [{"id": f"inbox-{index}"} for index in range(11)]}],
        "is:unread after:": [
            {"messages": [{"id": "today-1"}, {"id": "today-2"}, {"id": "today-3"}]},
            {"messages": [{"id": "yesterday-1"}, {"id": "yesterday-2"}, {"id": "yesterday-3"}, {"id": "yesterday-4"}]},
            {"messages": [{"id": f"week-{index}"} for index in range(9)]},
        ],
    }
    unread_range_index = {"value": 0}

    @app.get("/messages")
    async def messages(q: str = Query(default="")):
        if q == "is:unread in:inbox":
            return responses["is:unread in:inbox"][0]
        if q.startswith("is:unread after:"):
            current = unread_range_index["value"]
            unread_range_index["value"] += 1
            return responses["is:unread after:"][current]
        return {"messages": []}

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
    assert status.unread_week_count == 9


def build_google_fetch_app():
    app = FastAPI()

    @app.get("/messages")
    async def list_messages(q: str = Query(default=""), pageToken: str | None = None):
        if pageToken:
            return {"messages": []}
        assert q.startswith("in:inbox after:")
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


def test_gmail_mailbox_client_builds_local_time_window_queries():
    client = GmailMailboxClient()

    today_query = client.build_fetch_query("today", now=datetime(2026, 4, 2, 15, 30, 0).astimezone())
    last_hour_query = client.build_fetch_query("last_hour", now=datetime(2026, 4, 2, 15, 30, 0).astimezone())
    initial_query = client.build_fetch_query("initial_learning", now=datetime(2026, 4, 2, 15, 30, 0).astimezone())

    assert today_query.startswith("in:inbox after:")
    assert "before:" in today_query
    assert last_hour_query.startswith("in:inbox after:")
    assert initial_query.startswith("in:inbox after:")
