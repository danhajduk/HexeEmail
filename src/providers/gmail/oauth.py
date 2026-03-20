from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from providers.gmail.models import GmailOAuthSessionState
from providers.gmail.runtime import GmailRuntimeLayout


class GmailOAuthStateError(RuntimeError):
    pass


class GmailOAuthSessionManager:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def generate_state(self) -> str:
        return secrets.token_urlsafe(24)

    def create_session(self, account_id: str, *, correlation_id: str | None = None) -> GmailOAuthSessionState:
        session = GmailOAuthSessionState(
            state=self.generate_state(),
            account_id=account_id,
            correlation_id=correlation_id,
        )
        self.save_session(session)
        return session

    def save_session(self, session: GmailOAuthSessionState) -> GmailOAuthSessionState:
        path = self.layout.oauth_session_file(session.state)
        path.write_text(json.dumps(session.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(path, 0o600)
        return session

    def load_session(self, state: str) -> GmailOAuthSessionState:
        path = self.layout.oauth_session_file(state)
        if not path.exists():
            raise GmailOAuthStateError("OAuth state does not exist.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return GmailOAuthSessionState.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GmailOAuthStateError(f"OAuth state is corrupted: {exc}") from exc

    def validate_callback_state(self, state: str) -> GmailOAuthSessionState:
        session = self.load_session(state)
        now = datetime.now(UTC).replace(tzinfo=None)
        if session.consumed_at is not None:
            raise GmailOAuthStateError("OAuth state has already been consumed.")
        if session.expires_at <= now:
            raise GmailOAuthStateError("OAuth state has expired.")
        return session

    def consume_session(self, state: str) -> GmailOAuthSessionState:
        session = self.validate_callback_state(state)
        session.consumed_at = datetime.now(UTC).replace(tzinfo=None)
        self.save_session(session)
        return session

    def expire_stale_sessions(self) -> int:
        expired = 0
        now = datetime.now(UTC).replace(tzinfo=None)
        for path in self.layout.oauth_sessions_dir.glob("*.json"):
            try:
                session = self.load_session(path.stem)
            except GmailOAuthStateError:
                continue
            if session.consumed_at is not None:
                continue
            if session.expires_at <= now:
                session.consumed_at = now
                self.save_session(session)
                expired += 1
        return expired

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
