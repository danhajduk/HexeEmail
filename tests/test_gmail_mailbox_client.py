from __future__ import annotations

from fastapi import FastAPI, Query
from httpx import ASGITransport
import pytest

from providers.gmail.mailbox_client import GmailMailboxClient
from providers.gmail.models import GmailTokenRecord


def build_google_mailbox_app():
    app = FastAPI()
    counters = iter([3, 4, 9])

    @app.get("/messages")
    async def messages(q: str = Query(default="")):
        if q == "is:unread in:inbox":
            return {"resultSizeEstimate": 11}
        return {"resultSizeEstimate": next(counters)}

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
