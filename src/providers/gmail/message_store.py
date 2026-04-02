from __future__ import annotations

import calendar
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from providers.gmail.models import GmailMailboxStatus, GmailStoredMessage
from providers.gmail.runtime import GmailRuntimeLayout


class GmailMessageStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()
        self.path = self.layout.message_store_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gmail_messages (
                    account_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    thread_id TEXT,
                    subject TEXT,
                    sender TEXT,
                    recipients TEXT,
                    snippet TEXT,
                    label_ids TEXT,
                    received_at TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    raw_payload TEXT,
                    PRIMARY KEY (account_id, message_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_gmail_messages_account_received ON gmail_messages(account_id, received_at DESC)"
            )
            connection.commit()
        self._set_mode(self.path, 0o600)

    def upsert_messages(self, messages: list[GmailStoredMessage], *, now: datetime | None = None) -> int:
        if not messages:
            return 0
        fetched_at = (now or datetime.now().astimezone()).isoformat()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO gmail_messages (
                    account_id,
                    message_id,
                    thread_id,
                    subject,
                    sender,
                    recipients,
                    snippet,
                    label_ids,
                    received_at,
                    fetched_at,
                    raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, message_id) DO UPDATE SET
                    thread_id=excluded.thread_id,
                    subject=excluded.subject,
                    sender=excluded.sender,
                    recipients=excluded.recipients,
                    snippet=excluded.snippet,
                    label_ids=excluded.label_ids,
                    received_at=excluded.received_at,
                    fetched_at=excluded.fetched_at,
                    raw_payload=excluded.raw_payload
                """,
                [
                    (
                        message.account_id,
                        message.message_id,
                        message.thread_id,
                        message.subject,
                        message.sender,
                        "\n".join(message.recipients),
                        message.snippet,
                        "\n".join(message.label_ids),
                        message.received_at.isoformat(),
                        fetched_at,
                        message.raw_payload,
                    )
                    for message in messages
                ],
            )
            connection.commit()
        self.enforce_retention(now=now)
        return len(messages)

    def enforce_retention(self, *, now: datetime | None = None) -> int:
        cutoff = self._six_month_cutoff(now or datetime.now().astimezone())
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM gmail_messages WHERE received_at < ?",
                (cutoff.isoformat(),),
            )
            connection.commit()
            return cursor.rowcount if cursor.rowcount is not None else 0

    def list_messages(self, account_id: str, *, limit: int = 100) -> list[GmailStoredMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    account_id,
                    message_id,
                    thread_id,
                    subject,
                    sender,
                    recipients,
                    snippet,
                    label_ids,
                    received_at,
                    raw_payload
                FROM gmail_messages
                WHERE account_id = ?
                ORDER BY received_at DESC
                LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def count_messages(self, account_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM gmail_messages WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        return int(row["count"]) if row is not None else 0

    def account_summary(self, account_id: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    MAX(received_at) AS latest_received_at,
                    MAX(fetched_at) AS latest_fetched_at
                FROM gmail_messages
                WHERE account_id = ?
                """,
                (account_id,),
            ).fetchone()
        if row is None:
            return {"total_count": 0, "latest_received_at": None, "latest_fetched_at": None}
        return {
            "total_count": int(row["total_count"] or 0),
            "latest_received_at": row["latest_received_at"],
            "latest_fetched_at": row["latest_fetched_at"],
        }

    def mailbox_status(self, account_id: str, *, email_address: str | None = None, now: datetime | None = None) -> GmailMailboxStatus:
        local_now = (now or datetime.now().astimezone()).astimezone()
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        last_hour_start = local_now - timedelta(hours=1)
        rows = self._status_rows(account_id)

        unread_inbox_count = 0
        unread_today_count = 0
        unread_yesterday_count = 0
        unread_last_hour_count = 0

        for row in rows:
            label_ids = row["label_ids"].split("\n") if row["label_ids"] else []
            if "UNREAD" not in label_ids:
                continue
            received_at = self._normalize_message_time(datetime.fromisoformat(row["received_at"]), local_now)
            if "INBOX" in label_ids:
                unread_inbox_count += 1
            if today_start <= received_at < local_now + timedelta(seconds=1):
                unread_today_count += 1
            if yesterday_start <= received_at < today_start:
                unread_yesterday_count += 1
            if last_hour_start <= received_at <= local_now:
                unread_last_hour_count += 1

        return GmailMailboxStatus(
            account_id=account_id,
            email_address=email_address,
            status="ok",
            unread_inbox_count=unread_inbox_count,
            unread_today_count=unread_today_count,
            unread_yesterday_count=unread_yesterday_count,
            unread_last_hour_count=unread_last_hour_count,
            checked_at=local_now,
        )

    def _status_rows(self, account_id: str) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    label_ids,
                    received_at
                FROM gmail_messages
                WHERE account_id = ?
                """,
                (account_id,),
            ).fetchall()

    def _row_to_message(self, row: sqlite3.Row) -> GmailStoredMessage:
        recipients = row["recipients"].split("\n") if row["recipients"] else []
        label_ids = row["label_ids"].split("\n") if row["label_ids"] else []
        return GmailStoredMessage(
            account_id=row["account_id"],
            message_id=row["message_id"],
            thread_id=row["thread_id"],
            subject=row["subject"],
            sender=row["sender"],
            recipients=recipients,
            snippet=row["snippet"],
            label_ids=label_ids,
            received_at=datetime.fromisoformat(row["received_at"]),
            raw_payload=row["raw_payload"],
        )

    def _six_month_cutoff(self, now: datetime) -> datetime:
        year = now.year
        month = now.month - 6
        while month <= 0:
            month += 12
            year -= 1
        day = min(now.day, calendar.monthrange(year, month)[1])
        return now.replace(year=year, month=month, day=day)

    def _normalize_message_time(self, value: datetime, reference: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(reference.tzinfo)
        return value.replace(tzinfo=reference.tzinfo)

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
