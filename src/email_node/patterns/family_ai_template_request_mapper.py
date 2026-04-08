from __future__ import annotations

import re
from datetime import UTC, datetime

from email_node.patterns.pattern_generation_request import PatternGenerationRequest


def sanitize_family_template_identifier(value: str, *, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or fallback


def build_family_ai_template_request(
    phase4,
    *,
    expected_label: str,
    fallback_template_root: str,
) -> PatternGenerationRequest:
    hook = phase4.ai_template_hook
    if not isinstance(hook, dict):
        raise ValueError("missing ai_template_hook")
    profile_id = str(hook.get("profile_id") or phase4.profile_id or "").strip()
    if not profile_id:
        raise ValueError("missing profile_id")
    vendor_identity = str(hook.get("vendor_identity") or phase4.vendor_identity or phase4.sender_domain or "").strip()
    if not vendor_identity:
        raise ValueError("missing vendor_identity")
    body_text = str(hook.get("scrubbed_text") or "").strip()
    if not body_text:
        raise ValueError("missing scrubbed_text")
    template_root = sanitize_family_template_identifier(profile_id, fallback=fallback_template_root)
    vendor_root = sanitize_family_template_identifier(vendor_identity, fallback="generic")
    if not template_root.startswith(vendor_root):
        template_root = f"{vendor_root}_{template_root}"
    links = hook.get("extracted_links")
    links_json = links if isinstance(links, list) else []
    return PatternGenerationRequest(
        template_id=f"{template_root}.v1",
        profile_id=profile_id,
        template_version="v1",
        vendor_identity=vendor_identity,
        expected_label=expected_label,
        from_name=str(phase4.sender_name or vendor_identity).strip() or vendor_identity,
        from_email=str(phase4.sender_email or f"unknown@{vendor_root}.local").strip(),
        subject=str(phase4.subject or "").strip() or profile_id,
        received_at=datetime.now(UTC).isoformat(),
        body_text=body_text,
        body_html="",
        links_json=[item for item in links_json if isinstance(item, dict)],
    )
