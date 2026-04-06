from __future__ import annotations

from pathlib import Path

from email_node.shared_pipeline_core.families import get_flow_family_config
from email_node.shared_pipeline_core.profile_packs import load_profile_definition_pack
from email_node.shared_pipeline_core.profile_detector import SharedProfileDetectorEngine


class GmailOrderPhase3ProfileDetector(SharedProfileDetectorEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        config = get_flow_family_config("order", runtime_dir=runtime_dir)
        profile_pack = load_profile_definition_pack(config.profile_detector_pack, runtime_dir=runtime_dir)
        super().__init__(
            taxonomy=profile_pack.taxonomy,
            taxonomy_version=profile_pack.taxonomy_version,
            known_vendor_identities=profile_pack.known_vendor_identities,
            rules=profile_pack.load_rules(),
        )
