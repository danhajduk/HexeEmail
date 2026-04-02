from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from providers.gmail.models import GmailQuotaUsageSnapshot
from providers.gmail.runtime import GmailRuntimeLayout


class GmailQuotaLimitError(RuntimeError):
    pass


class GmailQuotaTracker:
    LIMIT_PER_MINUTE = 15000
    WINDOW_SECONDS = 60

    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()
        self.path = self.layout.quota_usage_path

    def reserve(self, account_id: str, units: int, operation: str, *, now: datetime | None = None) -> GmailQuotaUsageSnapshot:
        local_now = (now or datetime.now().astimezone()).astimezone()
        payload = self._load_payload()
        account_payload = payload.get(account_id, [])
        events = self._prune_events(account_payload, local_now)
        used = sum(int(event.get("units", 0)) for event in events)
        if used + units > self.LIMIT_PER_MINUTE:
            raise GmailQuotaLimitError(
                f"gmail quota limit would be exceeded for {account_id}: {used + units}/{self.LIMIT_PER_MINUTE} quota units in the last minute"
            )

        events.append(
            {
                "timestamp": local_now.isoformat(),
                "units": int(units),
                "operation": operation,
            }
        )
        payload[account_id] = events
        self._save_payload(payload)
        return self.snapshot(account_id, now=local_now)

    def snapshot(self, account_id: str, *, now: datetime | None = None) -> GmailQuotaUsageSnapshot:
        local_now = (now or datetime.now().astimezone()).astimezone()
        payload = self._load_payload()
        events = self._prune_events(payload.get(account_id, []), local_now)
        payload[account_id] = events
        self._save_payload(payload)

        recent_operations: dict[str, int] = {}
        for event in events:
            operation = str(event.get("operation") or "unknown")
            recent_operations[operation] = recent_operations.get(operation, 0) + int(event.get("units", 0))

        used = sum(int(event.get("units", 0)) for event in events)
        last_request_at = events[-1]["timestamp"] if events else None
        return GmailQuotaUsageSnapshot(
            account_id=account_id,
            limit_per_minute=self.LIMIT_PER_MINUTE,
            used_last_minute=used,
            remaining_last_minute=max(self.LIMIT_PER_MINUTE - used, 0),
            recent_operations=recent_operations,
            last_request_at=datetime.fromisoformat(last_request_at) if isinstance(last_request_at, str) else None,
        )

    def seconds_until_available(self, account_id: str, units: int, *, now: datetime | None = None) -> float:
        local_now = (now or datetime.now().astimezone()).astimezone()
        payload = self._load_payload()
        events = self._prune_events(payload.get(account_id, []), local_now)
        used = sum(int(event.get("units", 0)) for event in events)
        if used + units <= self.LIMIT_PER_MINUTE:
            return 0.0

        required_units = (used + units) - self.LIMIT_PER_MINUTE
        released_units = 0
        for event in events:
            released_units += int(event.get("units", 0))
            event_time = self._event_time(event)
            if event_time is None:
                continue
            wait_seconds = max((event_time + timedelta(seconds=self.WINDOW_SECONDS) - local_now).total_seconds(), 0.0)
            if released_units >= required_units:
                return wait_seconds
        return float(self.WINDOW_SECONDS)

    def _load_payload(self) -> dict[str, list[dict[str, object]]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _save_payload(self, payload: dict[str, list[dict[str, object]]]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(self.path, 0o600)

    def _prune_events(self, events: object, now: datetime) -> list[dict[str, object]]:
        if not isinstance(events, list):
            return []
        cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
        pruned: list[dict[str, object]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            event_time = self._event_time(event)
            if event_time is None:
                continue
            if event_time >= cutoff:
                pruned.append(event)
        return pruned

    def _event_time(self, event: dict[str, object]) -> datetime | None:
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str):
            return None
        try:
            return datetime.fromisoformat(timestamp)
        except ValueError:
            return None

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
