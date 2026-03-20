from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from providers.gmail.models import GmailTokenRecord
from providers.gmail.runtime import GmailRuntimeLayout


class GmailTokenStoreError(RuntimeError):
    pass


class GmailTokenStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def save_token(self, account_id: str, token_record: GmailTokenRecord) -> GmailTokenRecord:
        path = self.layout.token_file(account_id)
        path.write_text(json.dumps(token_record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(path, 0o600)
        return token_record

    def load_token(self, account_id: str) -> GmailTokenRecord | None:
        path = self.layout.token_file(account_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return GmailTokenRecord.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GmailTokenStoreError(f"gmail token record is invalid for account {account_id}: {exc}") from exc

    def delete_token(self, account_id: str) -> None:
        path = self.layout.token_file(account_id)
        if path.exists():
            path.unlink()

    def token_exists(self, account_id: str) -> bool:
        return self.layout.token_file(account_id).exists()

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
