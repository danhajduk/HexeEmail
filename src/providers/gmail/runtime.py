from __future__ import annotations

import os
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

    def account_file(self, account_id: str) -> Path:
        return self.accounts_dir / f"{account_id}.json"

    def oauth_session_file(self, state: str) -> Path:
        return self.oauth_sessions_dir / f"{state}.json"

    def ensure_layout(self) -> None:
        self.provider_dir.mkdir(parents=True, exist_ok=True)
        self.accounts_dir.mkdir(parents=True, exist_ok=True)
        self.oauth_sessions_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self.provider_config_path, "{}\n")

        self._set_mode(self.provider_dir, 0o700)
        self._set_mode(self.accounts_dir, 0o700)
        self._set_mode(self.oauth_sessions_dir, 0o700)
        self._set_mode(self.provider_config_path, 0o600)

    def _ensure_file(self, path: Path, contents: str) -> None:
        if path.exists():
            return
        path.write_text(contents, encoding="utf-8")

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
