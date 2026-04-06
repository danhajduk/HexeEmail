from __future__ import annotations

from email_node.shared_pipeline_core.scrub_engine import SharedScrubEngine, load_scrub_heuristic_pack


SCRUBBER_VERSION = "order-phase2-scrubber.v1"


class GmailOrderPhase2Scrubber(SharedScrubEngine):
    def __init__(self) -> None:
        super().__init__(
            heuristic_pack=load_scrub_heuristic_pack("providers.gmail.order_scrubber_rules"),
            scrubber_version=SCRUBBER_VERSION,
        )
