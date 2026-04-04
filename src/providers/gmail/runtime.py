from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GmailRuntimeLayout:
    runtime_dir: Path

    @property
    def provider_dir(self) -> Path:
        return self.runtime_dir / "providers" / "gmail"

    @property
    def provider_config_path(self) -> Path:
        return self.provider_dir / "provider_config.json"

    @property
    def accounts_dir(self) -> Path:
        return self.provider_dir / "accounts"

    @property
    def oauth_sessions_dir(self) -> Path:
        return self.provider_dir / "oauth_sessions"

    @property
    def oauth_state_secret_path(self) -> Path:
        return self.provider_dir / "oauth_state_secret"

    @property
    def mailbox_status_dir(self) -> Path:
        return self.provider_dir / "mailbox_status"

    @property
    def message_store_path(self) -> Path:
        return self.provider_dir / "messages.sqlite3"

    @property
    def fetch_schedule_state_path(self) -> Path:
        return self.provider_dir / "fetch_schedule_state.json"

    @property
    def quota_usage_path(self) -> Path:
        return self.provider_dir / "quota_usage.json"

    @property
    def label_cache_dir(self) -> Path:
        return self.provider_dir / "labels"

    @property
    def training_model_path(self) -> Path:
        return self.provider_dir / "training_model.pkl"

    @property
    def training_model_meta_path(self) -> Path:
        return self.provider_dir / "training_model_meta.json"

    def account_file(self, account_id: str) -> Path:
        return self.accounts_dir / f"{account_id}.json"

    def token_file(self, account_id: str) -> Path:
        return self.accounts_dir / f"{account_id}.token.json"

    def oauth_session_file(self, state: str) -> Path:
        return self.oauth_sessions_dir / f"{state}.json"

    def mailbox_status_file(self, account_id: str) -> Path:
        return self.mailbox_status_dir / f"{account_id}.json"

    def label_cache_file(self, account_id: str) -> Path:
        return self.label_cache_dir / f"{account_id}.json"

    def ensure_layout(self) -> None:
        self.provider_dir.mkdir(parents=True, exist_ok=True)
        self.accounts_dir.mkdir(parents=True, exist_ok=True)
        self.oauth_sessions_dir.mkdir(parents=True, exist_ok=True)
        self.mailbox_status_dir.mkdir(parents=True, exist_ok=True)
        self.label_cache_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self.provider_config_path, "{}\n")
        self._ensure_file(self.oauth_state_secret_path, f"{secrets.token_urlsafe(32)}\n")
        self._ensure_file(self.fetch_schedule_state_path, "{}\n")
        self._ensure_file(self.quota_usage_path, "{}\n")

        self._set_mode(self.provider_dir, 0o700)
        self._set_mode(self.accounts_dir, 0o700)
        self._set_mode(self.oauth_sessions_dir, 0o700)
        self._set_mode(self.mailbox_status_dir, 0o700)
        self._set_mode(self.label_cache_dir, 0o700)
        self._set_mode(self.provider_config_path, 0o600)
        self._set_mode(self.oauth_state_secret_path, 0o600)
        self._set_mode(self.fetch_schedule_state_path, 0o600)
        self._set_mode(self.quota_usage_path, 0o600)
        if self.message_store_path.exists():
            self._set_mode(self.message_store_path, 0o600)
        if self.training_model_path.exists():
            self._set_mode(self.training_model_path, 0o600)
        if self.training_model_meta_path.exists():
            self._set_mode(self.training_model_meta_path, 0o600)

    def _ensure_file(self, path: Path, contents: str) -> None:
        if path.exists():
            return
        path.write_text(contents, encoding="utf-8")

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
