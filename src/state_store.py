from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from models import RuntimeState, TrustMaterial


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
