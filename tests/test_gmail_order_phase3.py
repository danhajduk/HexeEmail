from __future__ import annotations

from providers.gmail.models import GmailPhase1Reference, GmailPhase2ScrubbedEmail
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector


def build_phase2_payload(
    *,
    subject: str = "Ordered: \"Sample Item\"",
    sender_name: str | None = "Amazon.com",
    sender_email: str | None = "auto-confirm@amazon.com",
    sender_domain: str | None = "amazon.com",
    scrubbed_text: str = "Thanks for your order!\nArriving tomorrow\nOrder # 112-1234567-1234567",
    normalized_lines: list[str] | None = None,
    scrub_status: str = "success",
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
        scrub_status=scrub_status,  # type: ignore[arg-type]
        transactional_quality="success" if scrub_status == "success" else "partial",
    )


def test_phase3_rejects_failed_phase2_payload():
    detector = GmailOrderPhase3ProfileDetector()
    phase2 = build_phase2_payload(scrubbed_text="", scrub_status="failed")

    result = detector.detect(phase2)

    assert result.profile_status == "failed"
    assert "phase2 scrub_status is failed" in result.profile_diagnostics


def test_phase3_detects_amazon_confirmation_profile():
    detector = GmailOrderPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject='Ordered: "ESP32-S3-BOX-3B Development..."',
        scrubbed_text=(
            "Thanks for your order, Slobodan!\n"
            "Ordered\n"
            "Arriving tomorrow\n"
            "Order # 112-0381957-4204214\n"
            "View or edit order"
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "amazon_order_confirmation"
    assert result.profile_subtype == "confirmation"
    assert result.vendor_identity == "amazon"
    assert result.profile_confidence_level in {"high", "medium"}


def test_phase3_detects_pickup_ready_profile():
    detector = GmailOrderPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Your Nectar - Hillsboro order is ready for pickup!",
        sender_name="Nectar - Hillsboro",
        sender_email="no-reply@dutchie.com",
        sender_domain="dutchie.com",
        scrubbed_text="Your order #147380483 is ready for pickup!",
    )

    result = detector.detect(phase2)

    assert result.profile_id == "pickup_ready_notification"
    assert result.profile_subtype == "pickup_ready"
    assert result.vendor_identity == "dutchie"


def test_phase3_detects_reservation_confirmation_profile():
    detector = GmailOrderPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Recreation.gov Reservation Confirmation",
        sender_name="Recreation.gov",
        sender_email="communications@recreation.gov",
        sender_domain="recreation.gov",
        scrubbed_text=(
            "Your Reservation Details!\n"
            "View/Print Reservation\n"
            "Hello Dan,\n"
            "Adventure awaits! Your reservation 0888904006-1"
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "reservation_confirmation"
    assert result.profile_subtype == "reservation_confirmed"
    assert result.profile_status in {"success", "partial"}


def test_phase3_downgrades_confidence_when_candidates_conflict():
    detector = GmailOrderPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject='Item cancelled successfully: "ESP32-S3-BOX-3B Development..."',
        sender_name="Amazon.com",
        sender_email="order-update@amazon.com",
        sender_domain="amazon.com",
        scrubbed_text=(
            "Order # 112-8349656-2435454\n"
            "Ready for pickup\n"
            "Item cancelled successfully\n"
            "Quantity: 1"
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_confidence_level in {"medium", "low"}
    assert any("confidence_downgrade" in item for item in result.profile_diagnostics)


def test_phase3_detects_upcoming_order_notice_profile():
    detector = GmailOrderPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Your Upcoming Commuter Benefits Order",
        sender_name=None,
        sender_email="no_reply@edenredbenefits.com",
        sender_domain="edenredbenefits.com",
        scrubbed_text=(
            "Your Upcoming Commuter Benefits Order\n"
            "Dear Slobodan,\n"
            "This is a reminder that you have a pending May 2026 Transit order."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "upcoming_order_notice"
    assert result.profile_subtype == "upcoming_order"
