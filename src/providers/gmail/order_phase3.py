from __future__ import annotations

from pathlib import Path

from email_node.shared_pipeline_core.profile_detector import SharedProfileDetectorEngine
from providers.gmail.models import (
    GmailPhase2ScrubbedEmail,
)
from providers.gmail.order_profile_taxonomy import (
    KNOWN_VENDOR_IDENTITIES,
    PROFILE_TAXONOMY,
    PROFILE_TAXONOMY_VERSION,
)
from providers.gmail.order_profile_rules import GmailOrderProfileRulesStore

class GmailOrderPhase3ProfileDetector(SharedProfileDetectorEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        super().__init__(
            taxonomy=PROFILE_TAXONOMY,
            taxonomy_version=PROFILE_TAXONOMY_VERSION,
            known_vendor_identities=KNOWN_VENDOR_IDENTITIES,
            rules=GmailOrderProfileRulesStore(runtime_dir).load(),
        )
