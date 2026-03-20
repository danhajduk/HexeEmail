from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from logging_utils import get_logger
from providers.gmail.models import GmailOAuthConfig
from providers.gmail.runtime import GmailRuntimeLayout
from providers.models import ProviderValidationResult


class GmailProviderConfigError(RuntimeError):
    pass


LOGGER = get_logger(__name__)


class GmailProviderConfigStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def load(self) -> GmailOAuthConfig:
        try:
            payload = json.loads(self.layout.provider_config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GmailProviderConfigError(f"gmail provider config is malformed: {exc}") from exc

        try:
            config = GmailOAuthConfig.model_validate(payload)
        except ValidationError as exc:
            raise GmailProviderConfigError(f"gmail provider config is invalid: {exc}") from exc
        LOGGER.info(
            "Gmail provider config loaded",
            extra={"event_data": {"enabled": config.enabled, "has_client_id": bool(config.client_id)}},
        )
        return config

    def save(self, config: GmailOAuthConfig) -> GmailOAuthConfig:
        payload = config.model_dump(mode="json")
        self.layout.provider_config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(self.layout.provider_config_path, 0o600)
        LOGGER.info(
            "Gmail provider config saved",
            extra={"event_data": {"enabled": config.enabled, "has_client_id": bool(config.client_id)}},
        )
        return config

    def validate(self, config: GmailOAuthConfig) -> ProviderValidationResult:
        return self.validate_static(config)

    @staticmethod
    def validate_static(config: GmailOAuthConfig) -> ProviderValidationResult:
        missing_fields: list[str] = []

        if not config.client_id:
            missing_fields.append("client_id")
        if not config.client_secret_ref:
            missing_fields.append("client_secret_ref")
        if not config.redirect_uri:
            missing_fields.append("redirect_uri")

        messages: list[str] = []
        if missing_fields:
            messages.append("Gmail OAuth configuration is incomplete.")
        LOGGER.info(
            "Gmail provider config validated",
            extra={"event_data": {"ok": not missing_fields, "missing_fields": missing_fields}},
        )

        return ProviderValidationResult(
            ok=not missing_fields,
            missing_fields=missing_fields,
            messages=messages,
        )

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
