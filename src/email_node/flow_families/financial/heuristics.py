from __future__ import annotations

from email_node.shared_pipeline_core.family_yaml import (
    build_scrub_heuristic_pack_from_yaml,
    load_flow_family_yaml_definition,
)


def _heuristic_pack():
    definition = load_flow_family_yaml_definition("financial")
    return build_scrub_heuristic_pack_from_yaml(definition)


HEURISTIC_PACK = _heuristic_pack()
IGNORE_LINE_PATTERNS = HEURISTIC_PACK.ignore_line_patterns
STOP_MARKER_PATTERNS = HEURISTIC_PACK.stop_marker_patterns
CHROME_LINE_PATTERNS = HEURISTIC_PACK.chrome_line_patterns
FOOTER_CUTOFF_PATTERNS = HEURISTIC_PACK.footer_cutoff_patterns
IMPORTANT_LINK_PATTERNS = HEURISTIC_PACK.important_link_patterns
TRACKING_HOST_PATTERNS = HEURISTIC_PACK.tracking_host_patterns
FILLER_ENTITY_PATTERNS = HEURISTIC_PACK.filler_entity_patterns
TRANSACTIONAL_ANCHOR_PATTERNS = HEURISTIC_PACK.transactional_anchor_patterns
PROMO_MARKER_PATTERNS = HEURISTIC_PACK.promo_marker_patterns


__all__ = [
    "CHROME_LINE_PATTERNS",
    "FILLER_ENTITY_PATTERNS",
    "FOOTER_CUTOFF_PATTERNS",
    "HEURISTIC_PACK",
    "IGNORE_LINE_PATTERNS",
    "IMPORTANT_LINK_PATTERNS",
    "PROMO_MARKER_PATTERNS",
    "STOP_MARKER_PATTERNS",
    "TRACKING_HOST_PATTERNS",
    "TRANSACTIONAL_ANCHOR_PATTERNS",
]
