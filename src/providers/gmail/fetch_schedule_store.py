from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from providers.gmail.models import GmailFetchScheduleState
from providers.gmail.runtime import GmailRuntimeLayout


class GmailFetchScheduleStoreError(RuntimeError):
    pass


class GmailFetchScheduleStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def load_state(self) -> GmailFetchScheduleState:
        path = self.layout.fetch_schedule_state_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return GmailFetchScheduleState.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GmailFetchScheduleStoreError(f"gmail fetch schedule state is invalid: {exc}") from exc

    def save_state(self, state: GmailFetchScheduleState) -> GmailFetchScheduleState:
        path = self.layout.fetch_schedule_state_path
        path.write_text(json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(path, 0o600)
        return state

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
