from __future__ import annotations

import asyncio

from email_node.flow_families.invoice.runtime import GmailInvoicePhase3ProfileDetector
from email_node.pipeline.invoice_flow import InvoiceFlowPipeline
from providers.gmail.models import GmailPhase1NormalizedEmail
from tests.test_gmail_order_phase3 import build_phase2_payload


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
    assert result["phase3"].profile_id == "invoice_ready"
    assert result["phase3"].profile_status in {"success", "partial"}
    assert result["phase4"].extraction_status == "unresolved"
    assert result["phase6"].decision == "review_needed"
    assert result["phase7"].persisted is True
    assert result["phase7"].trust_level == "review_needed"
    assert result["user_notification"].queued is True


def test_invoice_detector_matches_invoice_due():
    detector = GmailInvoicePhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Invoice due on April 18",
        sender_name="Stripe Billing",
        sender_email="billing@stripe.com",
        sender_domain="stripe.com",
        scrubbed_text=(
            "Invoice due.\n"
            "Amount due: $48.20.\n"
            "Pay this invoice before the due date."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "invoice_due"
    assert result.profile_confidence_level in {"high", "medium"}


def test_invoice_detector_matches_payment_confirmed():
    detector = GmailInvoicePhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Payment confirmed for your invoice",
        sender_name="QuickBooks",
        sender_email="payments@quickbooks.com",
        sender_domain="quickbooks.com",
        scrubbed_text=(
            "Payment confirmed.\n"
            "We received your payment and updated the invoice."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "payment_confirmed"
    assert result.profile_confidence_level in {"high", "medium"}
