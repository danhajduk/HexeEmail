from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from providers.gmail.runtime import GmailRuntimeLayout


class GmailLabelCacheStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def load(self, account_id: str) -> dict[str, object]:
        path = self.layout.label_cache_file(account_id)
        if not path.exists():
            return {"account_id": account_id, "labels": [], "checked_at": None}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"account_id": account_id, "labels": [], "checked_at": None}
        if not isinstance(payload, dict):
            return {"account_id": account_id, "labels": [], "checked_at": None}
        labels = payload.get("labels")
        checked_at = payload.get("checked_at")
        return {
            "account_id": account_id,
            "labels": labels if isinstance(labels, list) else [],
            "checked_at": checked_at if isinstance(checked_at, str) else None,
        }

    def save(self, account_id: str, labels: list[dict[str, object]], *, checked_at: datetime | None = None) -> dict[str, object]:
        payload = {
            "account_id": account_id,
            "checked_at": (checked_at or datetime.now().astimezone()).isoformat(),
            "labels": labels,
        }
        path = self.layout.label_cache_file(account_id)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(path, 0o600)
        return payload

    def id_name_map(self, account_id: str) -> dict[str, str]:
        payload = self.load(account_id)
        mapping: dict[str, str] = {}
        for item in payload.get("labels", []):
            if not isinstance(item, dict):
                continue
            label_id = item.get("id")
            name = item.get("name")
            if isinstance(label_id, str) and label_id and isinstance(name, str) and name:
                mapping[label_id] = name
        return mapping

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
