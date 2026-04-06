from __future__ import annotations

import importlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SharedProfileDefinitionPack:
    flow_family: str
    taxonomy_version: str
    taxonomy: dict[str, dict[str, str | None]]
    known_vendor_identities: dict[str, str]
    default_rules: dict[str, object]
    runtime_rules_path: Path

    def load_rules(self) -> dict[str, object]:
        rules = deepcopy(self.default_rules)
        if not self.runtime_rules_path.exists():
            return rules
        payload = json.loads(self.runtime_rules_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return rules
        return _deep_merge(rules, payload)


def load_profile_definition_pack(pack_reference: str, *, runtime_dir: Path | None = None) -> SharedProfileDefinitionPack:
    module = importlib.import_module(pack_reference)
    builder = getattr(module, "build_profile_definition_pack", None)
    if callable(builder):
        return builder(runtime_dir=runtime_dir)
    pack = getattr(module, "PROFILE_DEFINITION_PACK", None)
    if isinstance(pack, SharedProfileDefinitionPack):
        return pack
    raise ValueError(f"Unsupported profile definition pack: {pack_reference}")


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = deepcopy(value)
    return merged
