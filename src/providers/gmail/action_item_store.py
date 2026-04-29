from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from providers.gmail.models import GmailActionItem, GmailActionItemState
from providers.gmail.runtime import GmailRuntimeLayout


class GmailActionItemStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()
        self.path = self.layout.action_item_store_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gmail_action_items (
                    account_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    group_key TEXT,
                    source_message_id TEXT NOT NULL,
                    thread_id TEXT,
                    sender TEXT,
                    subject TEXT,
                    received_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    profile_id TEXT,
                    profile_type TEXT,
                    extracted_fields_json TEXT NOT NULL,
                    flow_output_json TEXT,
                    ai_decision_payload_json TEXT,
                    confidence REAL,
                    priority_score REAL NOT NULL DEFAULT 0,
                    snoozed_until TEXT,
                    reminder_at TEXT,
                    reminder_sent_at TEXT,
                    operator_note TEXT,
                    grouped_message_ids_json TEXT NOT NULL,
                    review_reasons_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    state_updated_at TEXT NOT NULL,
                    PRIMARY KEY (account_id, item_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gmail_action_items_account_state_priority
                ON gmail_action_items(account_id, state, priority_score DESC, received_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gmail_action_items_account_group
                ON gmail_action_items(account_id, group_key)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gmail_action_items_account_message
                ON gmail_action_items(account_id, source_message_id)
                """
            )
            connection.commit()
        self._set_mode(self.path, 0o600)

    def upsert_item(self, item: GmailActionItem, *, now: datetime | None = None) -> GmailActionItem:
        timestamp = now or datetime.now().astimezone()
        existing = self.get_item(item.account_id, item.item_id)
        created_at = item.created_at or (existing.created_at if existing is not None else timestamp)
        state_updated_at = (
            item.state_updated_at
            or (
                existing.state_updated_at
                if existing is not None and existing.state == item.state
                else timestamp
            )
        )
        stored = item.model_copy(update={"created_at": created_at, "updated_at": timestamp, "state_updated_at": state_updated_at})
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO gmail_action_items (
                    account_id,
                    item_id,
                    group_key,
                    source_message_id,
                    thread_id,
                    sender,
                    subject,
                    received_at,
                    state,
                    profile_id,
                    profile_type,
                    extracted_fields_json,
                    flow_output_json,
                    ai_decision_payload_json,
                    confidence,
                    priority_score,
                    snoozed_until,
                    reminder_at,
                    reminder_sent_at,
                    operator_note,
                    grouped_message_ids_json,
                    review_reasons_json,
                    created_at,
                    updated_at,
                    state_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, item_id) DO UPDATE SET
                    group_key = excluded.group_key,
                    source_message_id = excluded.source_message_id,
                    thread_id = excluded.thread_id,
                    sender = excluded.sender,
                    subject = excluded.subject,
                    received_at = excluded.received_at,
                    state = excluded.state,
                    profile_id = excluded.profile_id,
                    profile_type = excluded.profile_type,
                    extracted_fields_json = excluded.extracted_fields_json,
                    flow_output_json = excluded.flow_output_json,
                    ai_decision_payload_json = excluded.ai_decision_payload_json,
                    confidence = excluded.confidence,
                    priority_score = excluded.priority_score,
                    snoozed_until = excluded.snoozed_until,
                    reminder_at = excluded.reminder_at,
                    reminder_sent_at = excluded.reminder_sent_at,
                    operator_note = excluded.operator_note,
                    grouped_message_ids_json = excluded.grouped_message_ids_json,
                    review_reasons_json = excluded.review_reasons_json,
                    updated_at = excluded.updated_at,
                    state_updated_at = excluded.state_updated_at
                """,
                self._item_values(stored),
            )
            connection.commit()
        return stored

    def get_item(self, account_id: str, item_id: str) -> GmailActionItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM gmail_action_items
                WHERE account_id = ?
                  AND item_id = ?
                LIMIT 1
                """,
                (account_id, item_id),
            ).fetchone()
        return self._row_to_item(row) if row is not None else None

    def get_item_by_group_key(self, account_id: str, group_key: str) -> GmailActionItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM gmail_action_items
                WHERE account_id = ?
                  AND group_key = ?
                ORDER BY updated_at DESC, received_at DESC
                LIMIT 1
                """,
                (account_id, group_key),
            ).fetchone()
        return self._row_to_item(row) if row is not None else None

    def list_items(
        self,
        account_id: str,
        *,
        states: list[GmailActionItemState] | None = None,
        limit: int = 100,
    ) -> list[GmailActionItem]:
        params: list[object] = [account_id]
        state_filter = ""
        if states:
            placeholders = ",".join("?" for _ in states)
            state_filter = f"AND state IN ({placeholders})"
            params.extend(state.value for state in states)
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM gmail_action_items
                WHERE account_id = ?
                  {state_filter}
                ORDER BY priority_score DESC, received_at DESC, item_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def count_items(self, account_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM gmail_action_items WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        return int(row["count"]) if row is not None else 0

    def update_state(
        self,
        account_id: str,
        item_id: str,
        state: GmailActionItemState,
        *,
        now: datetime | None = None,
    ) -> GmailActionItem | None:
        item = self.get_item(account_id, item_id)
        if item is None:
            return None
        timestamp = now or datetime.now().astimezone()
        return self.upsert_item(item.model_copy(update={"state": state, "state_updated_at": timestamp}), now=timestamp)

    def _item_values(self, item: GmailActionItem) -> tuple[object, ...]:
        return (
            item.account_id,
            item.item_id,
            item.group_key,
            item.source_message_id,
            item.thread_id,
            item.sender,
            item.subject,
            item.received_at.isoformat(),
            item.state.value,
            item.profile_id,
            item.profile_type,
            self._json_dumps(item.extracted_fields),
            self._json_dumps(item.flow_output) if item.flow_output is not None else None,
            self._json_dumps(item.ai_decision_payload) if item.ai_decision_payload is not None else None,
            item.confidence,
            item.priority_score,
            self._datetime_to_text(item.snoozed_until),
            self._datetime_to_text(item.reminder_at),
            self._datetime_to_text(item.reminder_sent_at),
            item.operator_note,
            self._json_dumps(item.grouped_message_ids),
            self._json_dumps(item.review_reasons),
            self._datetime_to_text(item.created_at),
            self._datetime_to_text(item.updated_at),
            self._datetime_to_text(item.state_updated_at),
        )

    def _row_to_item(self, row: sqlite3.Row) -> GmailActionItem:
        return GmailActionItem(
            account_id=row["account_id"],
            item_id=row["item_id"],
            group_key=row["group_key"],
            source_message_id=row["source_message_id"],
            thread_id=row["thread_id"],
            sender=row["sender"],
            subject=row["subject"],
            received_at=datetime.fromisoformat(row["received_at"]),
            state=GmailActionItemState(row["state"]),
            profile_id=row["profile_id"],
            profile_type=row["profile_type"],
            extracted_fields=self._json_loads_object(row["extracted_fields_json"]),
            flow_output=self._json_loads_optional_object(row["flow_output_json"]),
            ai_decision_payload=self._json_loads_optional_object(row["ai_decision_payload_json"]),
            confidence=row["confidence"],
            priority_score=float(row["priority_score"] or 0),
            snoozed_until=self._datetime_from_text(row["snoozed_until"]),
            reminder_at=self._datetime_from_text(row["reminder_at"]),
            reminder_sent_at=self._datetime_from_text(row["reminder_sent_at"]),
            operator_note=row["operator_note"],
            grouped_message_ids=self._json_loads_list(row["grouped_message_ids_json"]),
            review_reasons=self._json_loads_list(row["review_reasons_json"]),
            created_at=self._datetime_from_text(row["created_at"]),
            updated_at=self._datetime_from_text(row["updated_at"]),
            state_updated_at=self._datetime_from_text(row["state_updated_at"]),
        )

    @staticmethod
    def _json_dumps(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _json_loads_object(value: object) -> dict[str, object]:
        if not isinstance(value, str) or not value:
            return {}
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _json_loads_optional_object(value: object) -> dict[str, object] | None:
        if not isinstance(value, str) or not value:
            return None
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else None

    @staticmethod
    def _json_loads_list(value: object) -> list[str]:
        if not isinstance(value, str) or not value:
            return []
        loaded = json.loads(value)
        return [str(item) for item in loaded] if isinstance(loaded, list) else []

    @staticmethod
    def _datetime_to_text(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _datetime_from_text(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        return datetime.fromisoformat(value)

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
