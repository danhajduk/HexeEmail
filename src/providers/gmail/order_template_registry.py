from __future__ import annotations

from pathlib import Path

from email_node.shared_pipeline_core.families import get_flow_family_config
from email_node.shared_pipeline_core.template_engine import SharedTemplateRegistry

TEMPLATE_SCHEMA_VERSION = "order-phase4-template.v1"
SUPPORTED_EXTRACTION_METHODS = {
    "regex",
    "line_contains",
    "line_after",
    "between_markers",
    "all_matches",
    "first_match",
    "link_by_label",
    "link_by_type",
}
SUPPORTED_TRANSFORMS = {
    "trim",
    "collapse_spaces",
    "normalize_currency",
    "normalize_order_number",
    "normalize_phone_number",
    "normalize_url",
}


class GmailOrderTemplateRegistry(SharedTemplateRegistry):
    def __init__(self, base_dir: Path | None = None) -> None:
        template_dir = base_dir or get_flow_family_config("order").template_dir
        legacy_dir = Path(__file__).resolve().parents[3] / "runtime" / "order_templates"
        super().__init__(
            base_dir=template_dir,
            fallback_dirs=[legacy_dir] if legacy_dir != template_dir else [],
            schema_version=TEMPLATE_SCHEMA_VERSION,
            supported_extraction_methods=SUPPORTED_EXTRACTION_METHODS,
            supported_transforms=SUPPORTED_TRANSFORMS,
        )
