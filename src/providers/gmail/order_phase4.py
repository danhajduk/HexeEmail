from __future__ import annotations

import re

from email_node.shared_pipeline_core import get_flow_family_config, load_validation_policy
from email_node.shared_pipeline_core.template_engine import SharedTemplateExecutionEngine
from providers.gmail.models import (
    GmailPhase1DiagnosticItem,
    GmailPhase3DetectedEmail,
)
from providers.gmail.order_template_registry import GmailOrderTemplateRegistry, TEMPLATE_SCHEMA_VERSION


EXTRACTOR_VERSION = "order-phase4-template-extractor.v1"


class GmailOrderPhase4Extractor(SharedTemplateExecutionEngine):
    def __init__(self, registry: GmailOrderTemplateRegistry | None = None) -> None:
        flow_config = get_flow_family_config("order")
        super().__init__(
            registry=registry or GmailOrderTemplateRegistry(),
            extractor_version=EXTRACTOR_VERSION,
            template_schema_version=TEMPLATE_SCHEMA_VERSION,
            validation_policy=load_validation_policy(flow_config.validation_policy),
        )

    def build_ai_template_hook(self, phase3: GmailPhase3DetectedEmail) -> dict[str, object]:
        phase2 = phase3.phase2_reference
        fallback_profile_id, fallback_profile_family, fallback_profile_subtype = self._fallback_profile_context(phase3)
        profile_id = phase3.profile_id or fallback_profile_id
        profile_family = phase3.profile_family or fallback_profile_family
        profile_subtype = phase3.profile_subtype or fallback_profile_subtype
        return {
            "sender_identity": phase3.sender_identity,
            "vendor_identity": phase3.vendor_identity,
            "profile_id": profile_id,
            "profile_family": profile_family,
            "profile_subtype": profile_subtype,
            "subject": phase3.subject,
            "scrubbed_text": phase2.scrubbed_text,
            "normalized_lines": list(phase2.normalized_lines),
            "extracted_links": [
                link.model_dump() if hasattr(link, "model_dump") else dict(link)
                for link in phase2.extracted_links
            ],
            "expected_output_schema": {
                "template_id": "candidate_template_id",
                "profile_id": profile_id,
                "template_version": "v1",
                "enabled": True,
                "match": {},
                "extract": {},
                "required_fields": [],
                "confidence_rules": {},
                "post_process": {},
            },
        }

    @staticmethod
    def _fallback_profile_context(phase3: GmailPhase3DetectedEmail) -> tuple[str | None, str | None, str | None]:
        subject = str(phase3.subject or "").strip().lower()
        body = str(phase3.phase2_reference.scrubbed_text or "").strip().lower()
        combined = "\n".join(part for part in [subject, body] if part)

        if not combined:
            return None, None, None
        if "cancel" in combined:
            return "generic_order_cancellation", "order", "cancellation"
        if any(term in combined for term in ["shipped", "delivered", "arriving", "out for delivery", "tracking"]):
            return "generic_order_status_update", "order", "status_update"
        if any(term in combined for term in ["reservation", "tickets", "ticket", "receipt", "purchase", "confirmation", "confirmed", "order"]):
            return "generic_order_confirmation", "order", "confirmation"
        return None, None, None

    @staticmethod
    def _diagnostics(items: list[str]) -> list[GmailPhase1DiagnosticItem]:
        diagnostics: list[GmailPhase1DiagnosticItem] = []
        for item in items:
            code = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_") or "diagnostic"
            diagnostics.append(GmailPhase1DiagnosticItem(code=code, detail=item))
        return diagnostics
