from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from providers.gmail.models import GmailMailboxStatus
from providers.gmail.runtime import GmailRuntimeLayout


class GmailMailboxStatusStoreError(RuntimeError):
    pass


class GmailMailboxStatusStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def save_status(self, status: GmailMailboxStatus) -> GmailMailboxStatus:
        path = self.layout.mailbox_status_file(status.account_id)
        path.write_text(json.dumps(status.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(path, 0o600)
        return status

    def load_status(self, account_id: str) -> GmailMailboxStatus | None:
        path = self.layout.mailbox_status_file(account_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return GmailMailboxStatus.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GmailMailboxStatusStoreError(f"gmail mailbox status is invalid for account {account_id}: {exc}") from exc

    def list_statuses(self) -> list[GmailMailboxStatus]:
        statuses: list[GmailMailboxStatus] = []
        for path in sorted(self.layout.mailbox_status_dir.glob("*.json")):
            account_id = path.stem
            loaded = self.load_status(account_id)
            if loaded is not None:
                statuses.append(loaded)
        return statuses

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
