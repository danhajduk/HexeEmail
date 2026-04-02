from __future__ import annotations

import calendar
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from providers.gmail.models import GmailStoredMessage
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
        fetched_at = (now or datetime.utcnow()).isoformat()
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
        cutoff = self._six_month_cutoff(now or datetime.utcnow())
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

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
