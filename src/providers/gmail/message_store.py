from __future__ import annotations

import calendar
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from providers.gmail.models import GmailMailboxStatus, GmailSpamhausCheck, GmailSpamhausSummary, GmailStoredMessage, GmailTrainingLabel
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
            self._ensure_column(connection, "gmail_messages", "local_label", "TEXT")
            self._ensure_column(connection, "gmail_messages", "local_label_confidence", "REAL")
            self._ensure_column(connection, "gmail_messages", "manual_classification", "INTEGER NOT NULL DEFAULT 0")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gmail_spamhaus_checks (
                    account_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    sender_email TEXT,
                    sender_domain TEXT,
                    checked INTEGER NOT NULL DEFAULT 0,
                    listed INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    checked_at TEXT,
                    detail TEXT,
                    PRIMARY KEY (account_id, message_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_gmail_spamhaus_checks_account_checked ON gmail_spamhaus_checks(account_id, checked_at DESC)"
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
                    raw_payload,
                    local_label,
                    local_label_confidence,
                    manual_classification
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

    def list_all_messages(self, account_id: str) -> list[GmailStoredMessage]:
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
                    raw_payload,
                    local_label,
                    local_label_confidence,
                    manual_classification
                FROM gmail_messages
                WHERE account_id = ?
                ORDER BY received_at DESC
                """,
                (account_id,),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

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

    def list_training_candidates(
        self,
        account_id: str,
        *,
        limit: int = 40,
        threshold: float = 0.6,
    ) -> list[GmailStoredMessage]:
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
                    raw_payload,
                    local_label,
                    local_label_confidence,
                    manual_classification
                FROM gmail_messages
                WHERE account_id = ?
                  AND (
                    local_label IS NULL
                    OR local_label = ?
                    OR COALESCE(local_label_confidence, 0) < ?
                  )
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (account_id, GmailTrainingLabel.UNKNOWN.value, threshold, limit),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def list_oldest_training_candidates(
        self,
        account_id: str,
        *,
        limit: int = 20,
        threshold: float = 0.6,
    ) -> list[GmailStoredMessage]:
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
                    raw_payload,
                    local_label,
                    local_label_confidence,
                    manual_classification
                FROM gmail_messages
                WHERE account_id = ?
                  AND (
                    local_label IS NULL
                    OR local_label = ?
                    OR COALESCE(local_label_confidence, 0) < ?
                  )
                ORDER BY received_at ASC
                LIMIT ?
                """,
                (account_id, GmailTrainingLabel.UNKNOWN.value, threshold, limit),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def list_manual_training_examples(self, account_id: str) -> list[GmailStoredMessage]:
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
                    raw_payload,
                    local_label,
                    local_label_confidence,
                    manual_classification
                FROM gmail_messages
                WHERE account_id = ?
                  AND manual_classification = 1
                  AND local_label IS NOT NULL
                  AND local_label != ?
                ORDER BY received_at DESC
                """,
                (account_id, GmailTrainingLabel.UNKNOWN.value),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def update_local_classification(
        self,
        account_id: str,
        message_id: str,
        *,
        label: GmailTrainingLabel,
        confidence: float,
        manual_classification: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE gmail_messages
                SET local_label = ?, local_label_confidence = ?, manual_classification = ?
                WHERE account_id = ? AND message_id = ?
                """,
                (label.value, confidence, 1 if manual_classification else 0, account_id, message_id),
            )
            connection.commit()

    def local_classification_summary(self, account_id: str) -> dict[str, object]:
        with self._connect() as connection:
            totals_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN local_label IS NOT NULL AND local_label != ? THEN 1 ELSE 0 END) AS classified_count,
                    SUM(CASE WHEN local_label = ? THEN 1 ELSE 0 END) AS unknown_count,
                    SUM(CASE WHEN manual_classification = 1 THEN 1 ELSE 0 END) AS manual_count
                FROM gmail_messages
                WHERE account_id = ?
                """,
                (GmailTrainingLabel.UNKNOWN.value, GmailTrainingLabel.UNKNOWN.value, account_id),
            ).fetchone()
            rows = connection.execute(
                """
                SELECT local_label, COUNT(*) AS count
                FROM gmail_messages
                WHERE account_id = ?
                  AND local_label IS NOT NULL
                GROUP BY local_label
                ORDER BY local_label
                """,
                (account_id,),
            ).fetchall()
        per_label = {
            row["local_label"]: int(row["count"] or 0)
            for row in rows
            if row["local_label"]
        }
        return {
            "total_count": int(totals_row["total_count"] or 0) if totals_row is not None else 0,
            "classified_count": int(totals_row["classified_count"] or 0) if totals_row is not None else 0,
            "unknown_count": int(totals_row["unknown_count"] or 0) if totals_row is not None else 0,
            "manual_count": int(totals_row["manual_count"] or 0) if totals_row is not None else 0,
            "per_label": per_label,
        }

    def list_messages_pending_spamhaus(self, account_id: str, *, limit: int | None = None) -> list[GmailStoredMessage]:
        query = """
            SELECT
                gm.account_id,
                gm.message_id,
                gm.thread_id,
                gm.subject,
                gm.sender,
                gm.recipients,
                gm.snippet,
                gm.label_ids,
                gm.received_at,
                gm.raw_payload
            FROM gmail_messages gm
            LEFT JOIN gmail_spamhaus_checks sc
              ON sc.account_id = gm.account_id AND sc.message_id = gm.message_id
            WHERE gm.account_id = ?
              AND COALESCE(sc.checked, 0) = 0
            ORDER BY gm.received_at DESC
        """
        params: list[object] = [account_id]
        if limit is not None:
            query = f"{query}\nLIMIT ?"
            params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._row_to_message(row) for row in rows]

    def upsert_spamhaus_check(self, check: GmailSpamhausCheck, *, now: datetime | None = None) -> GmailSpamhausCheck:
        checked_at = (check.checked_at or now or datetime.now().astimezone()).isoformat() if check.checked else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO gmail_spamhaus_checks (
                    account_id,
                    message_id,
                    sender_email,
                    sender_domain,
                    checked,
                    listed,
                    status,
                    checked_at,
                    detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, message_id) DO UPDATE SET
                    sender_email=excluded.sender_email,
                    sender_domain=excluded.sender_domain,
                    checked=excluded.checked,
                    listed=excluded.listed,
                    status=excluded.status,
                    checked_at=excluded.checked_at,
                    detail=excluded.detail
                """,
                (
                    check.account_id,
                    check.message_id,
                    check.sender_email,
                    check.sender_domain,
                    1 if check.checked else 0,
                    1 if check.listed else 0,
                    check.status,
                    checked_at,
                    check.detail,
                ),
            )
            connection.commit()
        return check.model_copy(update={"checked_at": datetime.fromisoformat(checked_at) if checked_at else None})

    def spamhaus_summary(self, account_id: str) -> GmailSpamhausSummary:
        with self._connect() as connection:
            checked_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS checked_count,
                    SUM(CASE WHEN listed = 1 THEN 1 ELSE 0 END) AS listed_count,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                    MAX(checked_at) AS latest_checked_at
                FROM gmail_spamhaus_checks
                WHERE account_id = ?
                  AND checked = 1
                """,
                (account_id,),
            ).fetchone()
            pending_row = connection.execute(
                """
                SELECT COUNT(*) AS pending_count
                FROM gmail_messages gm
                LEFT JOIN gmail_spamhaus_checks sc
                  ON sc.account_id = gm.account_id AND sc.message_id = gm.message_id
                WHERE gm.account_id = ?
                  AND COALESCE(sc.checked, 0) = 0
                """,
                (account_id,),
            ).fetchone()
        latest_checked_at = checked_row["latest_checked_at"] if checked_row is not None else None
        return GmailSpamhausSummary(
            account_id=account_id,
            checked_count=int(checked_row["checked_count"] or 0) if checked_row is not None else 0,
            pending_count=int(pending_row["pending_count"] or 0) if pending_row is not None else 0,
            listed_count=int(checked_row["listed_count"] or 0) if checked_row is not None else 0,
            error_count=int(checked_row["error_count"] or 0) if checked_row is not None else 0,
            latest_checked_at=datetime.fromisoformat(latest_checked_at) if isinstance(latest_checked_at, str) else None,
        )

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
            local_label=row["local_label"] if "local_label" in row.keys() else None,
            local_label_confidence=row["local_label_confidence"] if "local_label_confidence" in row.keys() else None,
            manual_classification=bool(row["manual_classification"]) if "manual_classification" in row.keys() else False,
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

    def _ensure_column(self, connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
