from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class RuntimeManager:
    def __init__(self, service: Any) -> None:
        self.service = service

    @staticmethod
    def default_runtime_task_state() -> dict[str, object]:
        return {
            "ai_calls_enabled": True,
            "request_status": "idle",
            "last_step": "none",
            "detail": "No runtime task request has been started yet.",
            "preview_response": None,
            "resolve_response": None,
            "authorize_response": None,
            "registration_request_payload": None,
            "execution_request_payload": None,
            "execution_response": None,
            "usage_summary_response": None,
            "started_at": None,
            "updated_at": None,
        }

    def runtime_task_state(self) -> dict[str, object]:
        state = dict(self.default_runtime_task_state())
        persisted = self.service.state.runtime_task_state if isinstance(self.service.state.runtime_task_state, dict) else {}
        state.update(persisted)
        return state

    def save_runtime_task_state(self, **updates: object) -> dict[str, object]:
        state = self.runtime_task_state()
        state.update(updates)
        self.service.state.runtime_task_state = state
        self.service.state_store.save(self.service.state)
        return state

    def runtime_ai_calls_enabled(self) -> bool:
        current = self.runtime_task_state()
        value = current.get("ai_calls_enabled")
        return True if value is None else bool(value)

    @staticmethod
    def runtime_ai_disabled_message() -> str:
        return "AI calls are disabled in Runtime Settings."

    def prompt_definition_dir(self) -> Path:
        directory = self.service.config.prompt_definition_dir
        resolved = directory if directory.is_absolute() else Path.cwd() / directory
        self.ensure_runtime_prompt_definitions(resolved)
        return resolved

    @staticmethod
    def _legacy_prompt_definition_dir() -> Path:
        return Path.cwd() / "src" / "runtime_prompts"

    def ensure_runtime_prompt_definitions(self, directory: Path) -> None:
        if directory.exists() and any(directory.glob("*.json")):
            return
        legacy_directory = self._legacy_prompt_definition_dir()
        if not legacy_directory.exists():
            return
        directory.mkdir(parents=True, exist_ok=True)
        for path in legacy_directory.glob("*.json"):
            target = directory / path.name
            if target.exists():
                continue
            shutil.copy2(path, target)

    def load_runtime_prompt_definitions(self) -> list[dict[str, object]]:
        directory = self.prompt_definition_dir()
        if not directory.exists():
            raise ValueError(f"Prompt definition directory does not exist: {directory}")
        prompt_definitions: list[dict[str, object]] = []
        for path in sorted(directory.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise ValueError(f"Prompt definition must be an object: {path}")
            if not payload.get("prompt_id"):
                raise ValueError(f"Prompt definition is missing prompt_id: {path}")
            if not payload.get("version"):
                raise ValueError(f"Prompt definition is missing version: {path}")
            prompt_definitions.append(payload)
        if not prompt_definitions:
            raise ValueError(f"No prompt definition JSON files found in {directory}")
        return prompt_definitions

    def load_runtime_prompt_definition(self, prompt_id: str) -> dict[str, object]:
        for prompt_definition in self.load_runtime_prompt_definitions():
            if prompt_definition.get("prompt_id") == prompt_id:
                return prompt_definition
        raise ValueError(f"Prompt definition not found for {prompt_id}")

    @staticmethod
    def prompt_registration_payload(prompt_definition: dict[str, object]) -> dict[str, object]:
        payload = dict(prompt_definition)
        payload.pop("node_runtime", None)
        return payload

    @staticmethod
    def prompt_update_payload(prompt_definition: dict[str, object]) -> dict[str, object]:
        payload = RuntimeManager.prompt_registration_payload(prompt_definition)
        payload.pop("prompt_id", None)
        payload.pop("service_id", None)
        payload.pop("task_family", None)
        return payload

    @staticmethod
    def normalize_target_api_base_url(target_api_base_url: str | None) -> str:
        target_base_url = str(target_api_base_url or "http://127.0.0.1:9002").strip().rstrip("/")
        return target_base_url[:-4] if target_base_url.endswith("/api") else target_base_url

    @staticmethod
    def prompt_sync_weekly_slot_key(now: datetime) -> str:
        iso_year, iso_week, _ = now.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    @staticmethod
    def runtime_monthly_authorize_slot_key(now: datetime) -> str | None:
        local_now = now.astimezone()
        if local_now.day != 1 or local_now.hour != 0 or local_now.minute >= 5:
            return None
        return f"{local_now.year:04d}-{local_now.month:02d}"

    @staticmethod
    def utc_iso_now() -> str:
        return datetime.now(UTC).isoformat()
