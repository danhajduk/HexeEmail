from __future__ import annotations

import asyncio

from email_node.pipeline import ActionRequiredFlowPipeline
from providers.gmail.models import GmailPhase1NormalizedEmail


def build_action_required_phase1_payload() -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="action-msg-1",
        thread_id="action-thread-1",
        provider_message_id="action-msg-1",
        provider_thread_id="action-thread-1",
        rfc_message_id="<action-msg-1@example.com>",
        subject="Action required: verify your account",
        sender_name="Security Team",
        sender_email="security@example.com",
        sender_domain="example.com",
        raw_sender="Security Team <security@example.com>",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=(
            "<html><body>"
            "<h1>Action required</h1>"
            "<p>Please verify your account before April 12.</p>"
            "<a href='https://example.com/verify'>Verify your account</a>"
            "</body></html>"
        ),
        selected_body_quality="rich_html",
        handoff_ready=True,
        validation_status="success",
    )


def test_action_required_flow_skeleton_runs_through_shared_core(tmp_path):
    result = asyncio.run(
        ActionRequiredFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_action_required_phase1_payload()
        )
    )

    assert result["flow_family"] == "action_required"
    assert result["phase2"].scrub_status in {"success", "partial", "failed"}
    assert result["phase3"].profile_status in {"success", "partial", "failed"}
    assert result["phase4"].extraction_status in {"unresolved", "failed"}
    assert result["phase6"].decision == "reject"
    assert result["phase7"].persisted is False
