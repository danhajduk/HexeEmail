from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from providers.gmail.models import GmailMailboxStatus, GmailTokenRecord


class GmailMailboxClientError(RuntimeError):
    pass


class GmailMailboxClient:
    MESSAGES_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def fetch_unread_status(self, *, token_record: GmailTokenRecord, email_address: str | None = None) -> GmailMailboxStatus:
        now = datetime.now().astimezone()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        tomorrow_start = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())

        unread_inbox_count = await self._count_query(token_record.access_token, "is:unread in:inbox")
        unread_today_count = await self._count_query(
            token_record.access_token,
            self._range_query(today_start, tomorrow_start),
        )
        unread_yesterday_count = await self._count_query(
            token_record.access_token,
            self._range_query(yesterday_start, today_start),
        )
        unread_week_count = await self._count_query(
            token_record.access_token,
            self._range_query(week_start, tomorrow_start),
        )

        return GmailMailboxStatus(
            account_id=token_record.account_id,
            email_address=email_address,
            status="ok",
            unread_inbox_count=unread_inbox_count,
            unread_today_count=unread_today_count,
            unread_yesterday_count=unread_yesterday_count,
            unread_week_count=unread_week_count,
            checked_at=datetime.utcnow(),
        )

    async def _count_query(self, access_token: str, query: str) -> int:
        response = await self._client.get(
            self.MESSAGES_ENDPOINT,
            params={"q": query, "maxResults": 1, "fields": "resultSizeEstimate"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise GmailMailboxClientError("gmail mailbox query returned invalid JSON") from exc

        if response.is_error:
            detail = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
            raise GmailMailboxClientError(detail or f"gmail mailbox query failed with status {response.status_code}")

        if not isinstance(payload, dict):
            raise GmailMailboxClientError("gmail mailbox query returned an invalid payload")
        estimate = payload.get("resultSizeEstimate")
        return int(estimate) if isinstance(estimate, int) else 0

    def _range_query(self, after: datetime, before: datetime) -> str:
        return f"is:unread in:inbox after:{int(after.timestamp())} before:{int(before.timestamp())}"

    async def aclose(self) -> None:
        await self._client.aclose()
