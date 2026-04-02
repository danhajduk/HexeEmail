from __future__ import annotations

import hmac
import json
import os
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode

from pydantic import ValidationError

from providers.gmail.models import GmailOAuthConfig
from providers.gmail.models import GmailOAuthSessionState
from providers.gmail.runtime import GmailRuntimeLayout


class GmailOAuthStateError(RuntimeError):
    pass


class GmailOAuthSessionManager:
    GOOGLE_AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    STATE_VERSION = 1
    STATE_TTL_SECONDS = 600

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
        client_id: str | None = None,
        correlation_id: str | None = None,
        core_id: str | None = None,
        node_id: str | None = None,
        flow_id: str | None = None,
    ) -> GmailOAuthSessionState:
        session = GmailOAuthSessionState(
            state=self.generate_state(),
            account_id=account_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_verifier=self.generate_code_verifier(),
            correlation_id=correlation_id,
            core_id=core_id,
            node_id=node_id,
            flow_id=flow_id,
        )
        if session.flow_id is None:
            session.flow_id = session.state
        self.save_session(session)
        return session

    def create_connect_session(
        self,
        account_id: str,
        oauth_config: GmailOAuthConfig,
        *,
        correlation_id: str | None = None,
        core_id: str | None = None,
        node_id: str | None = None,
    ) -> GmailOAuthSessionState:
        session = self.create_session(
            account_id,
            oauth_config.redirect_uri or "",
            client_id=oauth_config.client_id,
            correlation_id=correlation_id,
            core_id=core_id,
            node_id=node_id,
        )
        session.public_state = self.sign_public_state(session)
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
            "state": session.public_state or self.sign_public_state(session),
            "code_challenge": self.create_code_challenge(session.code_verifier),
            "code_challenge_method": "S256",
            "prompt": "consent",
        }
        return f"{self.GOOGLE_AUTH_BASE_URL}?{urlencode(params)}"

    def sign_public_state(self, session: GmailOAuthSessionState) -> str:
        payload = {
            "v": self.STATE_VERSION,
            "provider": "gmail",
            "client_id": session.client_id,
            "core_id": session.core_id,
            "node_id": session.node_id,
            "flow_id": session.flow_id,
            "account_id": session.account_id,
            "exp": int(session.expires_at.replace(tzinfo=UTC).timestamp()),
        }
        encoded_payload = self._encode_state_component(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(self._state_secret(), encoded_payload.encode("ascii"), sha256).digest()
        encoded_signature = self._encode_state_component(signature)
        return f"{encoded_payload}.{encoded_signature}"

    def verify_public_state(self, state: str) -> dict[str, object]:
        if not state:
            raise GmailOAuthStateError("Missing state.")
        try:
            encoded_payload, encoded_signature = state.split(".", 1)
        except ValueError as exc:
            raise GmailOAuthStateError("OAuth state is malformed.") from exc

        expected_signature = hmac.new(self._state_secret(), encoded_payload.encode("ascii"), sha256).digest()
        signature = self._decode_state_component(encoded_signature)
        if not hmac.compare_digest(signature, expected_signature):
            raise GmailOAuthStateError("OAuth state signature is invalid.")

        try:
            payload = json.loads(self._decode_state_component(encoded_payload).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GmailOAuthStateError("OAuth state payload is invalid.") from exc

        if payload.get("v") != self.STATE_VERSION:
            raise GmailOAuthStateError("OAuth state version is invalid.")
        if payload.get("provider") != "gmail":
            raise GmailOAuthStateError("OAuth state provider is invalid.")
        if not payload.get("client_id"):
            raise GmailOAuthStateError("OAuth state client id is missing.")
        if not payload.get("core_id"):
            raise GmailOAuthStateError("OAuth state core routing is missing.")
        if not payload.get("node_id"):
            raise GmailOAuthStateError("OAuth state node routing is missing.")
        if not payload.get("flow_id"):
            raise GmailOAuthStateError("OAuth state flow routing is missing.")
        expires_at = payload.get("exp")
        if not isinstance(expires_at, int):
            raise GmailOAuthStateError("OAuth state expiry is invalid.")
        now = int(datetime.now(UTC).timestamp())
        if expires_at < now:
            raise GmailOAuthStateError("OAuth state has expired.")
        return payload

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
        session = self._resolve_session(state)
        now = datetime.now(UTC).replace(tzinfo=None)
        if session.consumed_at is not None:
            raise GmailOAuthStateError("OAuth state has already been consumed.")
        if session.expires_at <= now:
            raise GmailOAuthStateError("OAuth state has expired.")
        return session

    def consume_session(self, state: str) -> GmailOAuthSessionState:
        session = self._resolve_session(state)
        now = datetime.now(UTC).replace(tzinfo=None)
        if session.consumed_at is not None:
            raise GmailOAuthStateError("OAuth state has already been consumed.")
        if session.expires_at <= now:
            raise GmailOAuthStateError("OAuth state has expired.")
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

    def _state_secret(self) -> bytes:
        return self.layout.oauth_state_secret_path.read_text(encoding="utf-8").strip().encode("utf-8")

    def _encode_state_component(self, value: bytes) -> str:
        return urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _decode_state_component(self, value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        try:
            return urlsafe_b64decode(value + padding)
        except Exception as exc:
            raise GmailOAuthStateError("OAuth state encoding is invalid.") from exc

    def _resolve_session(self, state: str) -> GmailOAuthSessionState:
        if "." not in state:
            return self.load_session(state)
        payload = self.verify_public_state(state)
        return self.load_session(str(payload["flow_id"]))
