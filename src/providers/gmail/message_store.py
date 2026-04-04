from __future__ import annotations

import calendar
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from providers.gmail.models import (
    GmailMailboxStatus,
    GmailSenderReputationInputs,
    GmailSenderReputationRecord,
    GmailSpamhausCheck,
    GmailSpamhausSummary,
    GmailStoredMessage,
    GmailTrainingLabel,
)
from providers.gmail.reputation import finalize_sender_reputation_record
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
            self._ensure_column(connection, "gmail_messages", "action_required_notification_sent", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "gmail_messages", "order_notification_sent", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "gmail_messages", "action_decision_payload", "TEXT")
            self._ensure_column(connection, "gmail_messages", "action_decision_prompt_version", "TEXT")
            self._ensure_column(connection, "gmail_messages", "action_decision_updated_at", "TEXT")
            self._ensure_column(connection, "gmail_messages", "action_decision_raw_response", "TEXT")
            self._ensure_column(connection, "gmail_messages", "action_decision_raw_response_updated_at", "TEXT")
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gmail_sender_reputation (
                    account_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    sender_value TEXT NOT NULL,
                    sender_email TEXT,
                    sender_domain TEXT,
                    group_domain TEXT,
                    reputation_state TEXT NOT NULL DEFAULT 'neutral',
                    derived_rating REAL NOT NULL DEFAULT 0,
                    rating REAL NOT NULL DEFAULT 0,
                    manual_rating REAL,
                    manual_rating_note TEXT,
                    manual_rating_updated_at TEXT,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    classification_positive_count INTEGER NOT NULL DEFAULT 0,
                    classification_negative_count INTEGER NOT NULL DEFAULT 0,
                    spamhaus_clean_count INTEGER NOT NULL DEFAULT 0,
                    spamhaus_listed_count INTEGER NOT NULL DEFAULT 0,
                    last_seen_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (account_id, entity_type, sender_value)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gmail_sender_reputation_account_updated
                ON gmail_sender_reputation(account_id, updated_at DESC)
                """
            )
            self._ensure_column(connection, "gmail_sender_reputation", "group_domain", "TEXT")
            self._ensure_column(connection, "gmail_sender_reputation", "derived_rating", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(connection, "gmail_sender_reputation", "manual_rating", "REAL")
            self._ensure_column(connection, "gmail_sender_reputation", "manual_rating_note", "TEXT")
            self._ensure_column(connection, "gmail_sender_reputation", "manual_rating_updated_at", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gmail_runtime_settings (
                    account_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (account_id, namespace, key)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gmail_runtime_settings_account_namespace_updated
                ON gmail_runtime_settings(account_id, namespace, updated_at DESC)
                """
            )
            connection.commit()
        self._set_mode(self.path, 0o600)

    def upsert_messages(self, messages: list[GmailStoredMessage], *, now: datetime | None = None) -> int:
        if not messages:
            return 0
        fetched_at = (now or datetime.now().astimezone()).isoformat()
        with self._connect() as connection:
            unique_message_ids = list(dict.fromkeys(message.message_id for message in messages))
            existing_ids: set[str] = set()
            account_id = messages[0].account_id
            for start in range(0, len(unique_message_ids), 500):
                batch_ids = unique_message_ids[start : start + 500]
                placeholders = ",".join("?" for _ in batch_ids)
                rows = connection.execute(
                    f"""
                    SELECT message_id
                    FROM gmail_messages
                    WHERE account_id = ?
                      AND message_id IN ({placeholders})
                    """,
                    (account_id, *batch_ids),
                ).fetchall()
                existing_ids.update(row["message_id"] for row in rows)
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
                    raw_payload,
                    local_label,
                    local_label_confidence,
                    manual_classification,
                    action_decision_payload,
                    action_decision_prompt_version,
                    action_decision_updated_at,
                    action_decision_raw_response,
                    action_decision_raw_response_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, message_id) DO UPDATE SET
                    thread_id=excluded.thread_id,
                    subject=excluded.subject,
                    sender=excluded.sender,
                    recipients=excluded.recipients,
                    snippet=excluded.snippet,
                    label_ids=excluded.label_ids,
                    received_at=excluded.received_at,
                    fetched_at=excluded.fetched_at,
                    raw_payload=excluded.raw_payload,
                    local_label=COALESCE(excluded.local_label, gmail_messages.local_label),
                    local_label_confidence=CASE
                        WHEN excluded.local_label IS NOT NULL THEN excluded.local_label_confidence
                        ELSE gmail_messages.local_label_confidence
                    END,
                    manual_classification=CASE
                        WHEN excluded.local_label IS NOT NULL THEN excluded.manual_classification
                        ELSE gmail_messages.manual_classification
                    END,
                    action_decision_payload=COALESCE(gmail_messages.action_decision_payload, excluded.action_decision_payload),
                    action_decision_prompt_version=COALESCE(
                        gmail_messages.action_decision_prompt_version,
                        excluded.action_decision_prompt_version
                    ),
                    action_decision_updated_at=COALESCE(
                        gmail_messages.action_decision_updated_at,
                        excluded.action_decision_updated_at
                    ),
                    action_decision_raw_response=COALESCE(
                        gmail_messages.action_decision_raw_response,
                        excluded.action_decision_raw_response
                    ),
                    action_decision_raw_response_updated_at=COALESCE(
                        gmail_messages.action_decision_raw_response_updated_at,
                        excluded.action_decision_raw_response_updated_at
                    )
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
                        message.local_label,
                        message.local_label_confidence,
                        int(bool(message.manual_classification)),
                        (
                            json.dumps(message.action_decision_payload, sort_keys=True, separators=(",", ":"), default=str)
                            if isinstance(message.action_decision_payload, dict)
                            else None
                        ),
                        message.action_decision_prompt_version,
                        message.action_decision_updated_at.isoformat() if message.action_decision_updated_at else None,
                        (
                            json.dumps(message.action_decision_raw_response, sort_keys=True, separators=(",", ":"), default=str)
                            if isinstance(message.action_decision_raw_response, dict)
                            else None
                        ),
                        (
                            message.action_decision_raw_response_updated_at.isoformat()
                            if message.action_decision_raw_response_updated_at
                            else None
                        ),
                    )
                    for message in messages
                ],
            )
            connection.commit()
        self.enforce_retention(now=now)
        return sum(1 for message_id in unique_message_ids if message_id not in existing_ids)

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
                    manual_classification,
                    action_decision_payload,
                    action_decision_prompt_version,
                    action_decision_updated_at,
                    action_decision_raw_response,
                    action_decision_raw_response_updated_at
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
                    manual_classification,
                    action_decision_payload,
                    action_decision_prompt_version,
                    action_decision_updated_at,
                    action_decision_raw_response,
                    action_decision_raw_response_updated_at
                FROM gmail_messages
                WHERE account_id = ?
                ORDER BY received_at DESC
                """,
                (account_id,),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def list_messages_received_since(self, account_id: str, *, since: datetime) -> list[GmailStoredMessage]:
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
                    manual_classification,
                    action_decision_payload,
                    action_decision_prompt_version,
                    action_decision_updated_at,
                    action_decision_raw_response,
                    action_decision_raw_response_updated_at
                FROM gmail_messages
                WHERE account_id = ?
                  AND received_at >= ?
                ORDER BY received_at DESC
                """,
                (account_id, since.isoformat()),
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

    def get_newest_unknown_message(self, account_id: str) -> GmailStoredMessage | None:
        with self._connect() as connection:
            row = connection.execute(
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
                  )
                ORDER BY received_at DESC
                LIMIT 1
                """,
                (account_id, GmailTrainingLabel.UNKNOWN.value),
            ).fetchone()
        return self._row_to_message(row) if row is not None else None

    def get_newest_message_by_labels(
        self,
        account_id: str,
        *,
        labels: list[GmailTrainingLabel],
    ) -> GmailStoredMessage | None:
        label_values = [label.value for label in labels]
        if not label_values:
            return None
        placeholders = ",".join("?" for _ in label_values)
        with self._connect() as connection:
            row = connection.execute(
                f"""
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
                    manual_classification,
                    action_decision_payload,
                    action_decision_prompt_version,
                    action_decision_updated_at,
                    action_decision_raw_response,
                    action_decision_raw_response_updated_at
                FROM gmail_messages
                WHERE account_id = ?
                  AND local_label IN ({placeholders})
                ORDER BY received_at DESC
                LIMIT 1
                """,
                (account_id, *label_values),
            ).fetchone()
        return self._row_to_message(row) if row is not None else None

    def get_message(self, account_id: str, message_id: str) -> GmailStoredMessage | None:
        with self._connect() as connection:
            row = connection.execute(
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
                    manual_classification,
                    action_decision_payload,
                    action_decision_prompt_version,
                    action_decision_updated_at,
                    action_decision_raw_response,
                    action_decision_raw_response_updated_at
                FROM gmail_messages
                WHERE account_id = ?
                  AND message_id = ?
                LIMIT 1
                """,
                (account_id, message_id),
            ).fetchone()
        return self._row_to_message(row) if row is not None else None

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

    def list_classified_messages_by_label(
        self,
        account_id: str,
        *,
        label: GmailTrainingLabel,
        limit: int = 40,
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
                  AND local_label = ?
                ORDER BY received_at DESC
                LIMIT ?
                """,
                (account_id, label.value, limit),
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

    def update_action_decision(
        self,
        account_id: str,
        message_id: str,
        *,
        payload: dict[str, object],
        prompt_version: str,
        updated_at: datetime | None = None,
    ) -> None:
        decision_updated_at = updated_at or datetime.now().astimezone()
        serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE gmail_messages
                SET action_decision_payload = ?, action_decision_prompt_version = ?, action_decision_updated_at = ?
                WHERE account_id = ? AND message_id = ?
                """,
                (serialized_payload, prompt_version, decision_updated_at.isoformat(), account_id, message_id),
            )
            connection.commit()

    def update_action_decision_debug_response(
        self,
        account_id: str,
        message_id: str,
        *,
        raw_response: dict[str, object],
        updated_at: datetime | None = None,
    ) -> None:
        debug_updated_at = updated_at or datetime.now().astimezone()
        serialized_payload = json.dumps(raw_response, sort_keys=True, separators=(",", ":"), default=str)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE gmail_messages
                SET action_decision_raw_response = ?, action_decision_raw_response_updated_at = ?
                WHERE account_id = ? AND message_id = ?
                """,
                (serialized_payload, debug_updated_at.isoformat(), account_id, message_id),
            )
            connection.commit()

    def get_runtime_setting(
        self,
        account_id: str,
        *,
        namespace: str,
        key: str,
    ) -> object | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT value_json
                FROM gmail_runtime_settings
                WHERE account_id = ?
                  AND namespace = ?
                  AND key = ?
                LIMIT 1
                """,
                (account_id, namespace, key),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["value_json"])
        except (TypeError, json.JSONDecodeError):
            return None

    def set_runtime_setting(
        self,
        account_id: str,
        *,
        namespace: str,
        key: str,
        value: object,
        updated_at: datetime | None = None,
    ) -> None:
        stored_at = updated_at or datetime.now().astimezone()
        serialized_value = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO gmail_runtime_settings (
                    account_id,
                    namespace,
                    key,
                    value_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_id, namespace, key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (account_id, namespace, key, serialized_value, stored_at.isoformat()),
            )
            connection.commit()

    def has_notification_label(self, account_id: str, message_id: str, label: str) -> bool:
        column_name = self._notification_flag_column_for_label(label)
        if column_name is None:
            return False
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT {column_name} AS notification_sent
                FROM gmail_messages
                WHERE account_id = ?
                  AND message_id = ?
                LIMIT 1
                """,
                (account_id, message_id),
            ).fetchone()
        if row is None:
            return False
        return bool(row["notification_sent"])

    def mark_notification_label_sent(self, account_id: str, message_id: str, label: str) -> None:
        column_name = self._notification_flag_column_for_label(label)
        if column_name is None:
            return
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT {column_name} AS notification_sent
                FROM gmail_messages
                WHERE account_id = ?
                  AND message_id = ?
                LIMIT 1
                """,
                (account_id, message_id),
            ).fetchone()
            if row is None:
                return
            if bool(row["notification_sent"]):
                return
            connection.execute(
                f"""
                UPDATE gmail_messages
                SET {column_name} = 1
                WHERE account_id = ?
                  AND message_id = ?
                """,
                (account_id, message_id),
            )
            connection.commit()

    def upsert_sender_reputation(
        self,
        record: GmailSenderReputationRecord,
        *,
        now: datetime | None = None,
    ) -> GmailSenderReputationRecord:
        updated_at = record.updated_at or now or datetime.now().astimezone()
        persisted = finalize_sender_reputation_record(record.model_copy(update={"updated_at": updated_at}))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO gmail_sender_reputation (
                    account_id,
                    entity_type,
                    sender_value,
                    sender_email,
                    sender_domain,
                    group_domain,
                    reputation_state,
                    derived_rating,
                    rating,
                    manual_rating,
                    manual_rating_note,
                    manual_rating_updated_at,
                    message_count,
                    classification_positive_count,
                    classification_negative_count,
                    spamhaus_clean_count,
                    spamhaus_listed_count,
                    last_seen_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, entity_type, sender_value) DO UPDATE SET
                    sender_email=excluded.sender_email,
                    sender_domain=excluded.sender_domain,
                    group_domain=excluded.group_domain,
                    reputation_state=excluded.reputation_state,
                    derived_rating=excluded.derived_rating,
                    rating=excluded.rating,
                    manual_rating=excluded.manual_rating,
                    manual_rating_note=excluded.manual_rating_note,
                    manual_rating_updated_at=excluded.manual_rating_updated_at,
                    message_count=excluded.message_count,
                    classification_positive_count=excluded.classification_positive_count,
                    classification_negative_count=excluded.classification_negative_count,
                    spamhaus_clean_count=excluded.spamhaus_clean_count,
                    spamhaus_listed_count=excluded.spamhaus_listed_count,
                    last_seen_at=excluded.last_seen_at,
                    updated_at=excluded.updated_at
                """,
                (
                    persisted.account_id,
                    persisted.entity_type,
                    persisted.sender_value,
                    persisted.sender_email,
                    persisted.sender_domain,
                    persisted.group_domain,
                    persisted.reputation_state,
                    persisted.derived_rating,
                    persisted.rating,
                    persisted.manual_rating,
                    persisted.manual_rating_note,
                    persisted.manual_rating_updated_at.isoformat() if persisted.manual_rating_updated_at else None,
                    persisted.inputs.message_count,
                    persisted.inputs.classification_positive_count,
                    persisted.inputs.classification_negative_count,
                    persisted.inputs.spamhaus_clean_count,
                    persisted.inputs.spamhaus_listed_count,
                    persisted.last_seen_at.isoformat() if persisted.last_seen_at else None,
                    updated_at.isoformat(),
                ),
            )
            connection.commit()
        return persisted

    def get_sender_reputation(
        self,
        account_id: str,
        *,
        entity_type: str,
        sender_value: str,
    ) -> GmailSenderReputationRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    account_id,
                    entity_type,
                    sender_value,
                    sender_email,
                    sender_domain,
                    group_domain,
                    reputation_state,
                    derived_rating,
                    rating,
                    manual_rating,
                    manual_rating_note,
                    manual_rating_updated_at,
                    message_count,
                    classification_positive_count,
                    classification_negative_count,
                    spamhaus_clean_count,
                    spamhaus_listed_count,
                    last_seen_at,
                    updated_at
                FROM gmail_sender_reputation
                WHERE account_id = ?
                  AND entity_type = ?
                  AND sender_value = ?
                LIMIT 1
                """,
                (account_id, entity_type, sender_value),
            ).fetchone()
        return self._row_to_sender_reputation(row) if row is not None else None

    def list_sender_reputations(
        self,
        account_id: str,
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[GmailSenderReputationRecord]:
        query = """
            SELECT
                account_id,
                entity_type,
                sender_value,
                sender_email,
                sender_domain,
                group_domain,
                reputation_state,
                derived_rating,
                rating,
                manual_rating,
                manual_rating_note,
                manual_rating_updated_at,
                message_count,
                classification_positive_count,
                classification_negative_count,
                spamhaus_clean_count,
                spamhaus_listed_count,
                last_seen_at,
                updated_at
            FROM gmail_sender_reputation
            WHERE account_id = ?
        """
        params: list[object] = [account_id]
        if entity_type is not None:
            query = f"{query}\n  AND entity_type = ?"
            params.append(entity_type)
        query = f"{query}\nORDER BY updated_at DESC, sender_value ASC\nLIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._row_to_sender_reputation(row) for row in rows]

    def replace_sender_reputations(
        self,
        account_id: str,
        records: list[GmailSenderReputationRecord],
        *,
        now: datetime | None = None,
    ) -> list[GmailSenderReputationRecord]:
        updated_at = now or datetime.now().astimezone()
        with self._connect() as connection:
            manual_rows = connection.execute(
                """
                SELECT
                    entity_type,
                    sender_value,
                    manual_rating,
                    manual_rating_note,
                    manual_rating_updated_at
                FROM gmail_sender_reputation
                WHERE account_id = ?
                """,
                (account_id,),
            ).fetchall()
            manual_by_key = {
                (row["entity_type"], row["sender_value"]): {
                    "manual_rating": float(row["manual_rating"]) if row["manual_rating"] is not None else None,
                    "manual_rating_note": row["manual_rating_note"],
                    "manual_rating_updated_at": (
                        datetime.fromisoformat(row["manual_rating_updated_at"])
                        if row["manual_rating_updated_at"]
                        else None
                    ),
                }
                for row in manual_rows
            }
            persisted_records: list[GmailSenderReputationRecord] = []
            for record in records:
                preserved = manual_by_key.get((record.entity_type, record.sender_value), {})
                merged = record.model_copy(
                    update={
                        "manual_rating": record.manual_rating if record.manual_rating is not None else preserved.get("manual_rating"),
                        "manual_rating_note": record.manual_rating_note if record.manual_rating_note is not None else preserved.get("manual_rating_note"),
                        "manual_rating_updated_at": (
                            record.manual_rating_updated_at
                            if record.manual_rating_updated_at is not None
                            else preserved.get("manual_rating_updated_at")
                        ),
                        "updated_at": record.updated_at or updated_at,
                    }
                )
                persisted_records.append(finalize_sender_reputation_record(merged))
            connection.execute(
                """
                DELETE FROM gmail_sender_reputation
                WHERE account_id = ?
                """,
                (account_id,),
            )
            connection.executemany(
                """
                INSERT INTO gmail_sender_reputation (
                    account_id,
                    entity_type,
                    sender_value,
                    sender_email,
                    sender_domain,
                    group_domain,
                    reputation_state,
                    derived_rating,
                    rating,
                    manual_rating,
                    manual_rating_note,
                    manual_rating_updated_at,
                    message_count,
                    classification_positive_count,
                    classification_negative_count,
                    spamhaus_clean_count,
                    spamhaus_listed_count,
                    last_seen_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.account_id,
                        record.entity_type,
                        record.sender_value,
                        record.sender_email,
                        record.sender_domain,
                        record.group_domain,
                        record.reputation_state,
                        record.derived_rating,
                        record.rating,
                        record.manual_rating,
                        record.manual_rating_note,
                        record.manual_rating_updated_at.isoformat() if record.manual_rating_updated_at else None,
                        record.inputs.message_count,
                        record.inputs.classification_positive_count,
                        record.inputs.classification_negative_count,
                        record.inputs.spamhaus_clean_count,
                        record.inputs.spamhaus_listed_count,
                        record.last_seen_at.isoformat() if record.last_seen_at else None,
                        (record.updated_at or updated_at).isoformat(),
                    )
                    for record in persisted_records
                ],
            )
            connection.commit()
        return persisted_records

    def set_sender_reputation_manual_rating(
        self,
        account_id: str,
        *,
        entity_type: str,
        sender_value: str,
        manual_rating: float | None,
        note: str | None = None,
        now: datetime | None = None,
    ) -> GmailSenderReputationRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    account_id,
                    entity_type,
                    sender_value,
                    sender_email,
                    sender_domain,
                    group_domain,
                    reputation_state,
                    derived_rating,
                    rating,
                    manual_rating,
                    manual_rating_note,
                    manual_rating_updated_at,
                    message_count,
                    classification_positive_count,
                    classification_negative_count,
                    spamhaus_clean_count,
                    spamhaus_listed_count,
                    last_seen_at,
                    updated_at
                FROM gmail_sender_reputation
                WHERE account_id = ?
                  AND entity_type = ?
                  AND sender_value = ?
                LIMIT 1
                """,
                (account_id, entity_type, sender_value),
            ).fetchone()
            if row is None:
                raise ValueError("sender reputation record was not found")
            existing = self._row_to_sender_reputation(row)
            updated_at = now or datetime.now().astimezone()
            normalized_note = (note or "").strip() or None
            normalized_rating = round(float(manual_rating), 2) if manual_rating is not None else None
            updated = finalize_sender_reputation_record(
                existing.model_copy(
                    update={
                        "manual_rating": normalized_rating,
                        "manual_rating_note": normalized_note,
                        "manual_rating_updated_at": updated_at if (normalized_rating is not None or normalized_note is not None) else None,
                        "updated_at": updated_at,
                    }
                )
            )
            connection.execute(
                """
                UPDATE gmail_sender_reputation
                SET group_domain = ?,
                    reputation_state = ?,
                    derived_rating = ?,
                    rating = ?,
                    manual_rating = ?,
                    manual_rating_note = ?,
                    manual_rating_updated_at = ?,
                    updated_at = ?
                WHERE account_id = ?
                  AND entity_type = ?
                  AND sender_value = ?
                """,
                (
                    updated.group_domain,
                    updated.reputation_state,
                    updated.derived_rating,
                    updated.rating,
                    updated.manual_rating,
                    updated.manual_rating_note,
                    updated.manual_rating_updated_at.isoformat() if updated.manual_rating_updated_at else None,
                    updated.updated_at.isoformat() if updated.updated_at else updated_at.isoformat(),
                    account_id,
                    entity_type,
                    sender_value,
                ),
            )
            connection.commit()
        return updated

    def local_classification_summary(self, account_id: str, *, high_confidence_threshold: float = 0.92) -> dict[str, object]:
        with self._connect() as connection:
            totals_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN local_label IS NOT NULL AND local_label != ? THEN 1 ELSE 0 END) AS classified_count,
                    SUM(CASE WHEN local_label = ? THEN 1 ELSE 0 END) AS unknown_count,
                    SUM(CASE WHEN manual_classification = 1 THEN 1 ELSE 0 END) AS manual_count,
                    SUM(
                        CASE
                            WHEN manual_classification = 0
                              AND local_label IS NOT NULL
                              AND local_label != ?
                              AND COALESCE(local_label_confidence, 0) >= ?
                            THEN 1
                            ELSE 0
                        END
                    ) AS high_confidence_count
                FROM gmail_messages
                WHERE account_id = ?
                """,
                (
                    GmailTrainingLabel.UNKNOWN.value,
                    GmailTrainingLabel.UNKNOWN.value,
                    GmailTrainingLabel.UNKNOWN.value,
                    high_confidence_threshold,
                    account_id,
                ),
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
            "high_confidence_count": int(totals_row["high_confidence_count"] or 0) if totals_row is not None else 0,
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

    def list_spamhaus_checked_message_ids(self, account_id: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT message_id
                FROM gmail_spamhaus_checks
                WHERE account_id = ?
                  AND checked = 1
                """,
                (account_id,),
            ).fetchall()
        return {str(row["message_id"]) for row in rows if row["message_id"]}

    def is_spamhaus_checked(self, account_id: str, message_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT checked
                FROM gmail_spamhaus_checks
                WHERE account_id = ?
                  AND message_id = ?
                """,
                (account_id, message_id),
            ).fetchone()
        return bool(row["checked"]) if row is not None else False

    def list_spamhaus_checks(self, account_id: str) -> list[GmailSpamhausCheck]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    account_id,
                    message_id,
                    sender_email,
                    sender_domain,
                    checked,
                    listed,
                    status,
                    checked_at,
                    detail
                FROM gmail_spamhaus_checks
                WHERE account_id = ?
                ORDER BY checked_at DESC, message_id ASC
                """,
                (account_id,),
            ).fetchall()
        return [
            GmailSpamhausCheck(
                account_id=row["account_id"],
                message_id=row["message_id"],
                sender_email=row["sender_email"],
                sender_domain=row["sender_domain"],
                checked=bool(row["checked"]),
                listed=bool(row["listed"]),
                status=row["status"],
                checked_at=datetime.fromisoformat(row["checked_at"]) if row["checked_at"] else None,
                detail=row["detail"],
            )
            for row in rows
        ]

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
            action_decision_payload=(
                json.loads(row["action_decision_payload"])
                if "action_decision_payload" in row.keys() and isinstance(row["action_decision_payload"], str) and row["action_decision_payload"]
                else None
            ),
            action_decision_prompt_version=(
                row["action_decision_prompt_version"] if "action_decision_prompt_version" in row.keys() else None
            ),
            action_decision_updated_at=(
                datetime.fromisoformat(row["action_decision_updated_at"])
                if "action_decision_updated_at" in row.keys() and row["action_decision_updated_at"]
                else None
            ),
            action_decision_raw_response=(
                json.loads(row["action_decision_raw_response"])
                if "action_decision_raw_response" in row.keys()
                and isinstance(row["action_decision_raw_response"], str)
                and row["action_decision_raw_response"]
                else None
            ),
            action_decision_raw_response_updated_at=(
                datetime.fromisoformat(row["action_decision_raw_response_updated_at"])
                if "action_decision_raw_response_updated_at" in row.keys() and row["action_decision_raw_response_updated_at"]
                else None
            ),
        )

    def _row_to_sender_reputation(self, row: sqlite3.Row) -> GmailSenderReputationRecord:
        return GmailSenderReputationRecord(
            account_id=row["account_id"],
            entity_type=row["entity_type"],
            sender_value=row["sender_value"],
            sender_email=row["sender_email"],
            sender_domain=row["sender_domain"],
            group_domain=row["group_domain"] if "group_domain" in row.keys() else None,
            reputation_state=row["reputation_state"],
            derived_rating=float(row["derived_rating"] or 0.0) if "derived_rating" in row.keys() else 0.0,
            rating=float(row["rating"] or 0.0),
            manual_rating=float(row["manual_rating"]) if "manual_rating" in row.keys() and row["manual_rating"] is not None else None,
            manual_rating_note=row["manual_rating_note"] if "manual_rating_note" in row.keys() else None,
            manual_rating_updated_at=(
                datetime.fromisoformat(row["manual_rating_updated_at"])
                if "manual_rating_updated_at" in row.keys() and row["manual_rating_updated_at"]
                else None
            ),
            inputs=GmailSenderReputationInputs(
                message_count=int(row["message_count"] or 0),
                classification_positive_count=int(row["classification_positive_count"] or 0),
                classification_negative_count=int(row["classification_negative_count"] or 0),
                spamhaus_clean_count=int(row["spamhaus_clean_count"] or 0),
                spamhaus_listed_count=int(row["spamhaus_listed_count"] or 0),
            ),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]) if row["last_seen_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
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

    def _notification_flag_column_for_label(self, label: str) -> str | None:
        if label == GmailTrainingLabel.ACTION_REQUIRED.value:
            return "action_required_notification_sent"
        if label == GmailTrainingLabel.ORDER.value:
            return "order_notification_sent"
        return None

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
