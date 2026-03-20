from __future__ import annotations

import json
import os
import secrets
from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from pathlib import Path
from hashlib import sha256
from urllib.parse import urlencode

from pydantic import ValidationError

from providers.gmail.models import GmailOAuthConfig
from providers.gmail.models import GmailOAuthSessionState
from providers.gmail.runtime import GmailRuntimeLayout


class GmailOAuthStateError(RuntimeError):
    pass


class GmailOAuthSessionManager:
    GOOGLE_AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"

    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def generate_state(self) -> str:
        return secrets.token_urlsafe(24)

    def generate_code_verifier(self) -> str:
        return secrets.token_urlsafe(64)

    def create_code_challenge(self, code_verifier: str) -> str:
        digest = sha256(code_verifier.encode("ascii")).digest()
        return urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def create_session(
        self,
        account_id: str,
        redirect_uri: str,
        *,
        correlation_id: str | None = None,
    ) -> GmailOAuthSessionState:
        session = GmailOAuthSessionState(
            state=self.generate_state(),
            account_id=account_id,
            redirect_uri=redirect_uri,
            code_verifier=self.generate_code_verifier(),
            correlation_id=correlation_id,
        )
        self.save_session(session)
        return session

    def create_connect_session(
        self,
        account_id: str,
        oauth_config: GmailOAuthConfig,
        redirect_uri: str,
        *,
        correlation_id: str | None = None,
    ) -> GmailOAuthSessionState:
        session = self.create_session(account_id, redirect_uri, correlation_id=correlation_id)
        session.authorization_url = self.build_connect_url(account_id, oauth_config, session)
        self.save_session(session)
        return session

    def build_connect_url(self, account_id: str, oauth_config: GmailOAuthConfig, session: GmailOAuthSessionState) -> str:
        params = {
            "client_id": oauth_config.client_id or "",
            "redirect_uri": session.redirect_uri,
            "response_type": "code",
            "scope": " ".join(oauth_config.requested_scopes.scopes),
            "access_type": "offline",
            "state": session.state,
            "login_hint": account_id,
            "code_challenge": self.create_code_challenge(session.code_verifier),
            "code_challenge_method": "S256",
            "prompt": "consent",
        }
        return f"{self.GOOGLE_AUTH_BASE_URL}?{urlencode(params)}"

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
