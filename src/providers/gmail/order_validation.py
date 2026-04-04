from __future__ import annotations

from providers.gmail.models import GmailPhase1NormalizedEmail


def validate_phase1_payload(payload: GmailPhase1NormalizedEmail) -> tuple[str, bool, list[str]]:
    diagnostics: list[str] = []
    if not payload.schema_version:
        diagnostics.append("schema_version is required")
    if not payload.provider:
        diagnostics.append("provider is required")
    if not payload.message_id:
        diagnostics.append("message_id is required")
    if not payload.sender_domain:
        diagnostics.append("sender_domain is required")
    if payload.selected_body_type == "none":
        diagnostics.append("selected_body_type must identify a handoff body")
    if not payload.selected_body_content:
        diagnostics.append("selected_body_content is required")
    if payload.selected_body_quality in {"empty", "corrupted"}:
        diagnostics.append(f"selected body quality is {payload.selected_body_quality}")
    if payload.raw_sender and not (payload.sender_name or payload.sender_email):
        diagnostics.append("canonical sender fields should be populated when sender source data exists")

    if not diagnostics:
        return "success", True, diagnostics
    if payload.message_id:
        return "partial", False, diagnostics
    return "failed", False, diagnostics
