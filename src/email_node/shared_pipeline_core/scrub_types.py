from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SharedScrubHeuristicPack:
    ignore_line_patterns: list[re.Pattern[str]]
    stop_marker_patterns: list[re.Pattern[str]]
    chrome_line_patterns: list[re.Pattern[str]]
    footer_cutoff_patterns: list[re.Pattern[str]]
    important_link_patterns: dict[str, re.Pattern[str]]
    tracking_host_patterns: list[re.Pattern[str]]
    filler_entity_patterns: list[re.Pattern[str]]
    transactional_anchor_patterns: list[re.Pattern[str]]
    promo_marker_patterns: list[re.Pattern[str]]
