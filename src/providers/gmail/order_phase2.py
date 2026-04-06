from __future__ import annotations

from email_node.shared_pipeline_core import get_flow_family_config
from email_node.shared_pipeline_core.scrub_engine import SharedScrubEngine, load_scrub_heuristic_pack


SCRUBBER_VERSION = "order-phase2-scrubber.v1"


class GmailOrderPhase2Scrubber(SharedScrubEngine):
    def __init__(self) -> None:
        flow_config = get_flow_family_config("order")
        super().__init__(
            heuristic_pack=load_scrub_heuristic_pack(flow_config.scrub_heuristic_pack),
            scrubber_version=SCRUBBER_VERSION,
        )
