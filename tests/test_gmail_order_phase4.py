from __future__ import annotations

from providers.gmail.models import GmailPhase1Reference, GmailPhase2ScrubbedEmail
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


def build_phase2_payload(
    *,
    subject: str,
    sender_name: str | None,
    sender_email: str | None,
    sender_domain: str | None,
    scrubbed_text: str,
    normalized_lines: list[str] | None = None,
) -> GmailPhase2ScrubbedEmail:
    return GmailPhase2ScrubbedEmail(
        phase1_reference=GmailPhase1Reference(
            schema_version="gmail.phase1.normalized.v1",
            provider="gmail",
            message_id="phase2-msg-1",
            thread_id="phase2-thread-1",
            provider_message_id="phase2-msg-1",
            provider_thread_id="phase2-thread-1",
            rfc_message_id="<phase2-msg-1@example.com>",
            subject=subject,
            sender_name=sender_name,
            sender_email=sender_email,
            sender_domain=sender_domain,
            selected_body_type="html",
            selected_body_source="parsed_mime_html_part",
            selected_body_selection_path="quality_comparison",
            handoff_ready=True,
            fetch_status="success",
            mime_parse_status="success",
            validation_status="success",
        ),
        message_id="phase2-msg-1",
        thread_id="phase2-thread-1",
        provider_message_id="phase2-msg-1",
        provider_thread_id="phase2-thread-1",
        rfc_message_id="<phase2-msg-1@example.com>",
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        sender_domain=sender_domain,
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        scrubbed_text=scrubbed_text,
        normalized_lines=normalized_lines or scrubbed_text.splitlines(),
        scrub_status="success",
        transactional_quality="success",
    )


def detect_phase3(phase2: GmailPhase2ScrubbedEmail):
    return GmailOrderPhase3ProfileDetector().detect(phase2)


def test_phase4_extracts_amazon_confirmation_fields():
    phase2 = build_phase2_payload(
        subject='Ordered: "ESP32-S3-BOX-3B Development..."',
        sender_name="Amazon.com",
        sender_email="auto-confirm@amazon.com",
        sender_domain="amazon.com",
        scrubbed_text=(
            "Thanks for your order, Slobodan!\n"
            "Ordered\n"
            "Arriving tomorrow\n"
            "Order # 112-0381957-4204214\n"
            "View or edit order\n"
            "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214\n"
            "* ESP32-S3-BOX-3B Development Board.\n"
            "Quantity: 1\n"
            "Grand Total:\n50 USD"
        ),
    )
    phase2.extracted_links.append(
        {
            "label": "View or edit order",
            "url": "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214",
            "normalized_url": "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214",
            "link_type": "order_action",
            "source": "plain_text",
            "is_tracking": False,
            "is_valid": True,
            "diagnostics": [],
        }
    )

    result = GmailOrderPhase4Extractor().extract(detect_phase3(phase2))

    assert result.template_id == "amazon_order_confirmation.v1"
    assert result.extracted_fields["order_number"].value == "112-0381957-4204214"
    assert result.extracted_fields["status"].value == "Arriving tomorrow"
    assert result.extracted_fields["order_action_url"].value == "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214"
    assert result.extraction_status in {"success", "partial"}


def test_phase4_extracts_pickup_ready_fields():
    phase2 = build_phase2_payload(
        subject="Your Nectar - Hillsboro order is ready for pickup!",
        sender_name="Nectar - Hillsboro",
        sender_email="no-reply@dutchie.com",
        sender_domain="dutchie.com",
        scrubbed_text="Your order #147380483 is ready for pickup!",
    )

    result = GmailOrderPhase4Extractor().extract(detect_phase3(phase2))

    assert result.template_id == "pickup_ready_notification.v1"
    assert result.extracted_fields["order_number"].value == "147380483"
    assert "ready for pickup" in str(result.extracted_fields["status"].value).lower()


def test_phase4_returns_unresolved_when_no_template_exists():
    phase2 = build_phase2_payload(
        subject="Recreation.gov Reservation Confirmation",
        sender_name="Recreation.gov",
        sender_email="communications@recreation.gov",
        sender_domain="recreation.gov",
        scrubbed_text="Your Reservation Details!\nAdventure awaits! Your reservation 0888904006-1",
    )

    result = GmailOrderPhase4Extractor().extract(detect_phase3(phase2))

    assert result.extraction_status == "unresolved"
    assert result.template_id is None
    assert result.ai_template_hook is not None
    assert any("no_template" in item for item in result.template_diagnostics)


def test_phase4_preserves_required_field_failures_in_confidence():
    phase2 = build_phase2_payload(
        subject='Ordered: "ESP32-S3-BOX-3B Development..."',
        sender_name="Amazon.com",
        sender_email="auto-confirm@amazon.com",
        sender_domain="amazon.com",
        scrubbed_text="Thanks for your order, Slobodan!\nOrdered\nView or edit order",
    )

    result = GmailOrderPhase4Extractor().extract(detect_phase3(phase2))

    assert result.extraction_confidence_level in {"medium", "low"}
    assert any("missing_required" in item for item in result.field_diagnostics)
