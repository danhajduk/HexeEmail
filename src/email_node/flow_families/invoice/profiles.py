from __future__ import annotations

from pathlib import Path

from email_node.shared_pipeline_core.family_yaml import (
    build_profile_definition_pack_from_yaml,
    load_flow_family_yaml_definition,
)
from email_node.shared_pipeline_core.profile_packs import SharedProfileDefinitionPack


def build_profile_definition_pack(*, runtime_dir: Path | None = None) -> SharedProfileDefinitionPack:
    definition = load_flow_family_yaml_definition("invoice", runtime_dir=runtime_dir)
    return build_profile_definition_pack_from_yaml(definition, runtime_dir=runtime_dir)


PROFILE_DEFINITION_PACK = build_profile_definition_pack()
PROFILE_TAXONOMY_VERSION = PROFILE_DEFINITION_PACK.taxonomy_version
PROFILE_TAXONOMY = PROFILE_DEFINITION_PACK.taxonomy
KNOWN_VENDOR_IDENTITIES = PROFILE_DEFINITION_PACK.known_vendor_identities
DEFAULT_PHASE3_RULES = PROFILE_DEFINITION_PACK.default_rules


__all__ = [
    "DEFAULT_PHASE3_RULES",
    "KNOWN_VENDOR_IDENTITIES",
    "PROFILE_DEFINITION_PACK",
    "PROFILE_TAXONOMY",
    "PROFILE_TAXONOMY_VERSION",
    "build_profile_definition_pack",
]
