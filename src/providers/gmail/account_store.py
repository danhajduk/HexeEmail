from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from providers.models import ProviderAccountRecord
from providers.gmail.runtime import GmailRuntimeLayout


class GmailAccountStoreError(RuntimeError):
    pass


class GmailAccountStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def save_account(self, account_record: ProviderAccountRecord) -> ProviderAccountRecord:
        path = self.layout.account_file(account_record.account_id)
        path.write_text(json.dumps(account_record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(path, 0o600)
        return account_record

    def load_account(self, account_id: str) -> ProviderAccountRecord | None:
        path = self.layout.account_file(account_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return ProviderAccountRecord.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GmailAccountStoreError(f"gmail account record is invalid for account {account_id}: {exc}") from exc

    def list_accounts(self) -> list[ProviderAccountRecord]:
        records: list[ProviderAccountRecord] = []
        for path in sorted(self.layout.accounts_dir.glob("*.json")):
            if path.name.endswith(".token.json"):
                continue
            records.append(self.load_account(path.stem))  # type: ignore[arg-type]
        return [record for record in records if record is not None]

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
