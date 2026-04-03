from __future__ import annotations

import asyncio
import calendar
import json
from datetime import datetime, timedelta
from email.utils import getaddresses

import httpx

from providers.gmail.models import GmailMailboxStatus, GmailStoredMessage, GmailTokenRecord
from providers.gmail.quota_tracker import GmailQuotaLimitError, GmailQuotaTracker


class GmailMailboxClientError(RuntimeError):
    pass


class GmailMailboxClient:
    MESSAGES_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    MESSAGE_ENDPOINT_TEMPLATE = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
    LABELS_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/labels"
    UNREAD_MESSAGES_QUERY = "is:unread"
    MESSAGE_LIST_QUOTA_UNITS = 5
    MESSAGE_GET_QUOTA_UNITS = 5
    LABEL_LIST_QUOTA_UNITS = 1
    QUOTA_SLOWDOWN_THRESHOLD = 0.90
    QUOTA_PAUSE_THRESHOLD = 0.99
    QUOTA_SLOWDOWN_DELAY_SECONDS = 0.5

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        quota_tracker: GmailQuotaTracker | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)
        self.quota_tracker = quota_tracker

    async def fetch_unread_status(self, *, token_record: GmailTokenRecord, email_address: str | None = None) -> GmailMailboxStatus:
        now = datetime.now().astimezone()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        tomorrow_start = today_start + timedelta(days=1)
        last_hour_start = now - timedelta(hours=1)

        unread_inbox_count = await self._count_query(token_record.account_id, token_record.access_token, "is:unread in:inbox")
        unread_today_count = await self._count_query(
            token_record.account_id,
            token_record.access_token,
            self._unread_range_query(today_start, tomorrow_start),
        )
        unread_yesterday_count = await self._count_query(
            token_record.account_id,
            token_record.access_token,
            self._unread_range_query(yesterday_start, today_start),
        )
        unread_last_hour_count = await self._count_query(
            token_record.account_id,
            token_record.access_token,
            self._unread_range_query(last_hour_start, now),
        )

        return GmailMailboxStatus(
            account_id=token_record.account_id,
            email_address=email_address,
            status="ok",
            unread_inbox_count=unread_inbox_count,
            unread_today_count=unread_today_count,
            unread_yesterday_count=unread_yesterday_count,
            unread_last_hour_count=unread_last_hour_count,
            checked_at=now,
        )

    async def fetch_unread_messages(self, *, token_record: GmailTokenRecord) -> list[GmailStoredMessage]:
        return await self.fetch_messages(token_record=token_record, query=self.UNREAD_MESSAGES_QUERY)

    async def fetch_labels(self, *, token_record: GmailTokenRecord) -> list[dict[str, object]]:
        response = await self._gmail_get(
            account_id=token_record.account_id,
            access_token=token_record.access_token,
            url=self.LABELS_ENDPOINT,
            params={"fields": "labels(id,name,type,messageListVisibility,labelListVisibility)"},
            operation="labels.list",
            quota_units=self.LABEL_LIST_QUOTA_UNITS,
        )
        payload = self._json_payload(response, "gmail labels fetch")
        if response.is_error:
            detail = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
            raise GmailMailboxClientError(detail or f"gmail labels fetch failed with status {response.status_code}")
        if not isinstance(payload, dict):
            raise GmailMailboxClientError("gmail labels fetch returned an invalid payload")
        labels: list[dict[str, object]] = []
        for item in payload.get("labels") or []:
            if not isinstance(item, dict):
                continue
            label_id = item.get("id")
            name = item.get("name")
            if not isinstance(label_id, str) or not label_id or not isinstance(name, str) or not name:
                continue
            if label_id.startswith("Label_"):
                continue
            labels.append(
                {
                    "id": label_id,
                    "name": name,
                    "type": item.get("type") if isinstance(item.get("type"), str) else None,
                    "message_list_visibility": item.get("messageListVisibility")
                    if isinstance(item.get("messageListVisibility"), str)
                    else None,
                    "label_list_visibility": item.get("labelListVisibility")
                    if isinstance(item.get("labelListVisibility"), str)
                    else None,
                }
            )
        labels.sort(key=lambda item: str(item.get("name", "")).lower())
        return labels

    async def _count_query(self, account_id: str, access_token: str, query: str) -> int:
        response = await self._gmail_get(
            account_id=account_id,
            access_token=access_token,
            url=self.MESSAGES_ENDPOINT,
            params={"q": query, "maxResults": 1, "fields": "resultSizeEstimate"},
            operation="messages.list",
            quota_units=self.MESSAGE_LIST_QUOTA_UNITS,
        )
        payload = self._json_payload(response, "gmail mailbox query")
        if response.is_error:
            detail = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
            raise GmailMailboxClientError(detail or f"gmail mailbox query failed with status {response.status_code}")
        if not isinstance(payload, dict):
            raise GmailMailboxClientError("gmail mailbox query returned an invalid payload")
        estimate = payload.get("resultSizeEstimate")
        return int(estimate) if isinstance(estimate, int) else 0

    def _unread_range_query(self, after: datetime, before: datetime) -> str:
        return f"is:unread after:{int(after.timestamp())} before:{int(before.timestamp())}"

    def build_fetch_query(self, window: str, *, now: datetime | None = None) -> str:
        local_now = (now or datetime.now()).astimezone()
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        next_second = local_now + timedelta(seconds=1)

        if window == "initial_learning":
            start = self._months_ago(local_now, 6)
            return self._all_mail_range_query(start, next_second)
        if window == "yesterday":
            return self._all_mail_range_query(yesterday_start, today_start)
        if window == "today":
            return self._all_mail_range_query(today_start, next_second)
        if window == "last_hour":
            return self._all_mail_range_query(local_now - timedelta(hours=1), next_second)
        raise GmailMailboxClientError(f"unsupported gmail fetch window: {window}")

    async def fetch_messages(self, *, token_record: GmailTokenRecord, query: str) -> list[GmailStoredMessage]:
        messages: list[GmailStoredMessage] = []
        async for batch_messages in self.iter_message_batches(token_record=token_record, query=query):
            messages.extend(batch_messages)
        return messages

    async def iter_message_batches(self, *, token_record: GmailTokenRecord, query: str):
        async for message_ids in self._iter_message_id_pages(token_record.account_id, token_record.access_token, query):
            if not message_ids:
                continue
            for start in range(0, len(message_ids), 10):
                batch = message_ids[start : start + 10]
                yield await self._fetch_message_batch(token_record, batch)

    async def _list_message_ids(self, account_id: str, access_token: str, query: str) -> list[str]:
        message_ids: list[str] = []
        async for page_ids in self._iter_message_id_pages(account_id, access_token, query):
            message_ids.extend(page_ids)
        return message_ids

    async def _iter_message_id_pages(self, account_id: str, access_token: str, query: str):
        page_token: str | None = None
        while True:
            params: dict[str, object] = {"q": query, "maxResults": 100, "fields": "messages/id,nextPageToken"}
            if page_token:
                params["pageToken"] = page_token
            response = await self._gmail_get(
                account_id=account_id,
                access_token=access_token,
                url=self.MESSAGES_ENDPOINT,
                params=params,
                operation="messages.list",
                quota_units=self.MESSAGE_LIST_QUOTA_UNITS,
            )
            payload = self._json_payload(response, "gmail mailbox listing")
            if response.is_error:
                detail = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
                raise GmailMailboxClientError(detail or f"gmail mailbox listing failed with status {response.status_code}")
            if not isinstance(payload, dict):
                raise GmailMailboxClientError("gmail mailbox listing returned an invalid payload")
            page_message_ids: list[str] = []
            for item in payload.get("messages") or []:
                message_id = item.get("id") if isinstance(item, dict) else None
                if isinstance(message_id, str) and message_id:
                    page_message_ids.append(message_id)
            if page_message_ids:
                yield page_message_ids
            next_page_token = payload.get("nextPageToken")
            if not isinstance(next_page_token, str) or not next_page_token:
                break
            page_token = next_page_token

    async def _fetch_message_batch(self, token_record: GmailTokenRecord, message_ids: list[str]) -> list[GmailStoredMessage]:
        results = await asyncio.gather(
            *[
                self._fetch_message(token_record.access_token, token_record.account_id, message_id)
                for message_id in message_ids
            ]
        )
        return list(results)

    async def _fetch_message(self, access_token: str, account_id: str, message_id: str) -> GmailStoredMessage:
        response = await self._gmail_get(
            account_id=account_id,
            access_token=access_token,
            url=self.MESSAGE_ENDPOINT_TEMPLATE.format(message_id=message_id),
            params={
                "format": "metadata",
                "metadataHeaders": ["From", "To", "Cc", "Subject", "List-Unsubscribe"],
                "fields": "id,threadId,labelIds,snippet,internalDate,payload/headers,payload/parts/filename",
            },
            operation="messages.get",
            quota_units=self.MESSAGE_GET_QUOTA_UNITS,
        )
        payload = self._json_payload(response, "gmail message fetch")
        if response.is_error:
            detail = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
            raise GmailMailboxClientError(detail or f"gmail message fetch failed with status {response.status_code}")
        if not isinstance(payload, dict):
            raise GmailMailboxClientError("gmail message fetch returned an invalid payload")

        headers = payload.get("payload", {}).get("headers") if isinstance(payload.get("payload"), dict) else []
        header_map: dict[str, str] = {}
        if isinstance(headers, list):
            for header in headers:
                if isinstance(header, dict):
                    name = header.get("name")
                    value = header.get("value")
                    if isinstance(name, str) and isinstance(value, str):
                        header_map[name.lower()] = value

        recipient_values = [header_map.get("to", ""), header_map.get("cc", "")]
        recipients = [address for _, address in getaddresses(recipient_values) if address]
        internal_date_value = payload.get("internalDate")
        received_at = self._parse_internal_date(internal_date_value)

        return GmailStoredMessage(
            account_id=account_id,
            message_id=message_id,
            thread_id=payload.get("threadId") if isinstance(payload.get("threadId"), str) else None,
            subject=header_map.get("subject"),
            sender=header_map.get("from"),
            recipients=recipients,
            snippet=payload.get("snippet") if isinstance(payload.get("snippet"), str) else None,
            label_ids=[label for label in payload.get("labelIds") or [] if isinstance(label, str)],
            received_at=received_at,
            raw_payload=json.dumps(payload, separators=(",", ":")),
        )

    def _parse_internal_date(self, value: object) -> datetime:
        if isinstance(value, str) and value.isdigit():
            return datetime.fromtimestamp(int(value) / 1000).astimezone()
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000).astimezone()
        return datetime.now().astimezone()

    def _json_payload(self, response: httpx.Response, operation: str) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise GmailMailboxClientError(f"{operation} returned invalid JSON") from exc

    async def _gmail_get(
        self,
        *,
        account_id: str,
        access_token: str,
        url: str,
        params: dict[str, object],
        operation: str,
        quota_units: int,
    ) -> httpx.Response:
        if self.quota_tracker is not None:
            snapshot = self.quota_tracker.snapshot(account_id)
            used_ratio = (
                snapshot.used_last_minute / snapshot.limit_per_minute
                if snapshot.limit_per_minute > 0
                else 0.0
            )
            if used_ratio >= self.QUOTA_PAUSE_THRESHOLD:
                pause_seconds = max(
                    self.quota_tracker.seconds_until_available(account_id, quota_units),
                    self.QUOTA_SLOWDOWN_DELAY_SECONDS,
                )
                await asyncio.sleep(pause_seconds)
            elif used_ratio >= self.QUOTA_SLOWDOWN_THRESHOLD:
                await asyncio.sleep(self.QUOTA_SLOWDOWN_DELAY_SECONDS)
            try:
                self.quota_tracker.reserve(account_id, quota_units, operation)
            except GmailQuotaLimitError as exc:
                raise GmailMailboxClientError(str(exc)) from exc
        return await self._client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def _inbox_range_query(self, after: datetime, before: datetime) -> str:
        return f"in:inbox after:{int(after.timestamp())} before:{int(before.timestamp())}"

    def _all_mail_range_query(self, after: datetime, before: datetime) -> str:
        return f"after:{int(after.timestamp())} before:{int(before.timestamp())}"

    def _inbox_date_query(self, after: datetime, before: datetime) -> str:
        return f"in:inbox after:{self._gmail_date(after)} before:{self._gmail_date(before)}"

    def _inbox_after_date_query(self, after: datetime) -> str:
        return f"in:inbox after:{self._gmail_date(after)}"

    def _gmail_date(self, value: datetime) -> str:
        local_value = value.astimezone()
        return f"{local_value.year}/{local_value.month}/{local_value.day}"

    def _months_ago(self, value: datetime, months: int) -> datetime:
        year = value.year
        month = value.month - months
        while month <= 0:
            month += 12
            year -= 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)

    async def aclose(self) -> None:
        await self._client.aclose()
