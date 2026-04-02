from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from models import OperatorConfig, RuntimeState, TrustMaterial


class StateCorruptionError(RuntimeError):
    pass


class JsonFileStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write_json(self, payload: dict[str, Any], *, mode: int | None = None) -> None:
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        os.replace(temp_path, self.path)
        if mode is not None:
            os.chmod(self.path, mode)


class RuntimeStateStore(JsonFileStore):
    def load(self) -> RuntimeState:
        if not self.path.exists():
            return RuntimeState()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return RuntimeState.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise StateCorruptionError(f"runtime state is corrupted: {exc}") from exc

    def save(self, state: RuntimeState) -> RuntimeState:
        state.updated_at = datetime.utcnow()
        self._write_json(state.model_dump(mode="json"))
        return state


class OperatorConfigStore(JsonFileStore):
    def load(self, *, defaults: OperatorConfig | None = None) -> OperatorConfig:
        if not self.path.exists():
            return defaults or OperatorConfig()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            loaded = OperatorConfig.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise StateCorruptionError(f"operator config is corrupted: {exc}") from exc

        merged = defaults or OperatorConfig()
        return OperatorConfig(
            core_base_url=loaded.core_base_url or merged.core_base_url,
            node_name=loaded.node_name or merged.node_name,
            selected_task_capabilities=loaded.selected_task_capabilities or merged.selected_task_capabilities,
        )

    def save(self, config: OperatorConfig) -> OperatorConfig:
        self._write_json(config.model_dump(mode="json"))
        return config


class TrustMaterialStore(JsonFileStore):
    def load(self) -> TrustMaterial | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return TrustMaterial.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise StateCorruptionError(f"trust material is corrupted: {exc}") from exc

    def save(self, material: TrustMaterial) -> TrustMaterial:
        self._write_json(material.model_dump(mode="json"), mode=0o600)
        return material

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
