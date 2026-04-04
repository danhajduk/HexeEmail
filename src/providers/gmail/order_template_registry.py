from __future__ import annotations

import json
from pathlib import Path


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


class GmailOrderTemplateRegistry:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[3] / "runtime" / "order_templates"

    def list_templates(self) -> list[dict[str, object]]:
        if not self.base_dir.exists():
            return []
        templates: list[dict[str, object]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_path"] = str(path)
            templates.append(payload)
        return templates

    def lookup(
        self,
        *,
        profile_id: str,
        vendor_identity: str | None,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]], list[str]]:
        matches: list[tuple[int, dict[str, object]]] = []
        diagnostics: list[str] = []
        for template in self.list_templates():
            if not template.get("enabled", True):
                continue
            if template.get("profile_id") != profile_id:
                continue
            score = 0
            match = template.get("match", {})
            if match.get("vendor_identity") and match.get("vendor_identity") == vendor_identity:
                score += 5
            if not match.get("vendor_identity"):
                score += 1
            matches.append((score, template))
        matches.sort(key=lambda item: (item[0], str(item[1].get("template_version", ""))), reverse=True)
        if not matches:
            diagnostics.append(f"template_lookup:no_template_for_profile:{profile_id}")
            return None, [], diagnostics
        primary = matches[0][1]
        fallbacks = [item[1] for item in matches[1:3]]
        diagnostics.append(f"template_lookup:resolved:{primary.get('template_id')}")
        return primary, fallbacks, diagnostics

    def validate_template(self, template: dict[str, object]) -> list[str]:
        diagnostics: list[str] = []
        required_keys = {
            "template_id",
            "profile_id",
            "template_version",
            "enabled",
            "match",
            "extract",
            "required_fields",
            "confidence_rules",
            "post_process",
        }
        missing = sorted(required_keys - set(template))
        if missing:
            diagnostics.append(f"template_schema:missing_keys:{','.join(missing)}")
        if template.get("schema_version") != TEMPLATE_SCHEMA_VERSION:
            diagnostics.append("template_schema:unexpected_schema_version")
        extract = template.get("extract", {})
        if not isinstance(extract, dict):
            diagnostics.append("template_schema:extract_must_be_object")
            return diagnostics
        for field_name, rule in extract.items():
            if not isinstance(rule, dict):
                diagnostics.append(f"template_schema:field_rule_not_object:{field_name}")
                continue
            method = rule.get("method")
            if method not in SUPPORTED_EXTRACTION_METHODS:
                diagnostics.append(f"template_schema:unsupported_method:{field_name}:{method}")
            for transform in rule.get("transforms", []) or []:
                if transform not in SUPPORTED_TRANSFORMS:
                    diagnostics.append(f"template_schema:unsupported_transform:{field_name}:{transform}")
        return diagnostics
