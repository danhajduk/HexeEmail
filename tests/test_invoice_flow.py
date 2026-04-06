from __future__ import annotations

import asyncio

from email_node.pipeline.invoice_flow import InvoiceFlowPipeline
from providers.gmail.models import GmailPhase1NormalizedEmail


def build_invoice_phase1_payload() -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="invoice-msg-1",
        thread_id="invoice-thread-1",
        provider_message_id="invoice-msg-1",
        provider_thread_id="invoice-thread-1",
        rfc_message_id="<invoice-msg-1@example.com>",
        subject="Your invoice is ready",
        sender_name="Example Billing",
        sender_email="billing@example.com",
        sender_domain="example.com",
        raw_sender="Example Billing <billing@example.com>",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=(
            "<html><body>"
            "<h1>Your invoice is ready</h1>"
            "<p>Please review your latest billing document.</p>"
            "<a href='https://example.com/invoices'>View invoice</a>"
            "</body></html>"
        ),
        selected_body_quality="rich_html",
        handoff_ready=True,
        validation_status="success",
    )


def test_invoice_flow_skeleton_runs_through_shared_core(tmp_path):
    result = asyncio.run(
        InvoiceFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_invoice_phase1_payload()
        )
    )

    assert result["flow_family"] == "invoice"
    assert result["phase2"].scrub_status in {"success", "partial", "failed"}
    assert result["phase3"].profile_status in {"partial", "failed"}
    assert result["phase4"].extraction_status == "failed"
    assert result["phase6"].decision == "review_needed"
    assert result["phase7"].persisted is True
    assert result["phase7"].trust_level == "review_needed"
    assert result["user_notification"].queued is True
