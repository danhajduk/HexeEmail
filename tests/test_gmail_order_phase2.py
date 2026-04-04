from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport
import pytest

from providers.gmail.mailbox_client import GmailMailboxClient
from providers.gmail.models import GmailPhase1NormalizedEmail, GmailTokenRecord
from providers.gmail.order_flow import GmailOrderPhase1Processor
from providers.gmail.order_phase2 import GmailOrderPhase2Scrubber


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gmail_phase1"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def build_phase1_payload(
    *,
    selected_body_type: str = "html",
    selected_body_content: str = "<div>Track package</div>",
    handoff_ready: bool = True,
) -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="phase1-msg-1",
        thread_id="phase1-thread-1",
        provider_message_id="phase1-msg-1",
        provider_thread_id="phase1-thread-1",
        rfc_message_id="<phase1-msg-1@example.com>",
        subject="Order update",
        sender_name="Order Sender",
        sender_email="orders@example.com",
        sender_domain="example.com",
        raw_sender="Order Sender <orders@example.com>",
        selected_body_type=selected_body_type,  # type: ignore[arg-type]
        selected_body_source="parsed_mime_html_part" if selected_body_type == "html" else "parsed_mime_text_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=selected_body_content,
        selected_body_quality="rich_html" if selected_body_type == "html" else "usable_text",
        handoff_ready=handoff_ready,
        validation_status="success" if handoff_ready else "partial",
    )


def test_phase2_scrubber_rejects_non_handoff_ready_phase1():
    scrubber = GmailOrderPhase2Scrubber()
    phase1 = build_phase1_payload(handoff_ready=False)

    result = scrubber.scrub(phase1)

    assert result.scrub_status == "failed"
    assert "phase1 payload is not ready for handoff" in result.scrub_diagnostics
    assert result.phase1_reference.message_id == phase1.message_id


def test_phase2_html_extraction_strips_hidden_content_and_extracts_links():
    scrubber = GmailOrderPhase2Scrubber()
    phase1 = build_phase1_payload(
        selected_body_content=(
            "<html><head><style>.x{color:red}</style><script>ignore()</script></head>"
            "<body>"
            '<div style="display:none">View in browser</div>'
            "<div>Your Orders</div>"
            "<p>Track your package now</p>"
            '<a href="https://example.com/track/123">Track package</a>'
            '<img src="https://tracking.example.com/pixel" width="1" height="1" />'
            "<p>Privacy Notice</p>"
            "<p>Footer that should be cut</p>"
            "</body></html>"
        ),
    )

    result = scrubber.scrub(phase1)

    assert result.scrub_status == "partial"
    assert "Track your package now" in result.scrubbed_text
    assert "Your Orders" not in result.scrubbed_text
    assert "Privacy Notice" not in result.scrubbed_text
    assert result.hidden_content_stripped is True
    assert any(link.link_type == "tracking_action" for link in result.extracted_links)
    assert "chrome:your orders" in result.applied_rules
    assert result.phase1_reference.subject == "Order update"


def test_phase2_plain_text_normalization_and_link_capture():
    scrubber = GmailOrderPhase2Scrubber()
    phase1 = build_phase1_payload(
        selected_body_type="text",
        selected_body_content=(
            "Your order is ready  \r\n"
            "for pickup.\r\n\r\n"
            "Track here: https://example.com/track/abc123 \r\n"
            "Order number:\r\n"
            "112-8876120-3805015\r\n"
        ),
    )

    result = scrubber.scrub(phase1)

    assert result.scrub_status == "partial"
    assert "Your order is ready for pickup." in result.scrubbed_text
    assert "Order number:" in result.scrubbed_text
    assert any(link.url == "https://example.com/track/abc123" for link in result.extracted_links)
    assert result.scrub_metrics.links_extracted >= 1
    assert result.transactional_quality == "partial"


def test_phase2_targets_transactional_block_and_order_action_links():
    scrubber = GmailOrderPhase2Scrubber()
    phase1 = build_phase1_payload(
        selected_body_content=(
            "<html><body>"
            "<div>Your Orders</div>"
            "<div>-20% $43.96</div>"
            "<div>-11% $39.90</div>"
            "<div>Thanks for your order, Slobodan!</div>"
            "<div>Arriving tomorrow</div>"
            "<div>Order #</div>"
            "<div>112-0381957-4204214</div>"
            '<a href=\"https://www.amazon.com/gp/r.html?U=https%3A%2F%2Fwww.amazon.com%2Fyour-orders%2Forder-details%3ForderID%3D112-0381957-4204214\">View or edit order</a>'
            "<div>* ESP32-S3-BOX-3B Development Board.</div>"
            "<div>Quantity: 1</div>"
            "<div>50 USD</div>"
            "<div>Grand Total:</div>"
            "<div>50 USD</div>"
            "<div>Buy Again</div>"
            "</body></html>"
        ),
    )
    phase1 = phase1.model_copy(
        update={
            "decoded_text": (
                "Thanks for your order, Slobodan!\n\n"
                "Arriving tomorrow\n\n"
                "Order #\n112-0381957-4204214\n\n"
                "View or edit order\nhttps://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214\n\n"
                "* ESP32-S3-BOX-3B Development Board.\n"
                "Quantity: 1\n"
                "50 USD\n\n"
                "Grand Total:\n50 USD\n"
            )
        }
    )

    result = scrubber.scrub(phase1)

    assert result.scrub_status == "success"
    assert "Thanks for your order, Slobodan!" in result.scrubbed_text
    assert "Arriving tomorrow" in result.scrubbed_text
    assert "Order # 112-0381957-4204214" in result.scrubbed_text
    assert "Quantity: 1" in result.scrubbed_text
    assert "Grand Total:" in result.scrubbed_text
    assert "-20% $43.96" not in result.scrubbed_text
    assert "Buy Again" not in result.scrubbed_text
    assert result.extracted_links
    assert result.extracted_links[0].link_type == "order_action"
    assert result.extracted_links[0].normalized_url == "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214"
    assert result.extracted_links[0].is_valid is True
    assert result.transactional_quality == "success"
    assert any("merged block" in detail.detail for detail in result.stage_diagnostics["transactional_targeting"])


def test_phase2_downgrades_when_missing_critical_order_anchor():
    scrubber = GmailOrderPhase2Scrubber()
    phase1 = build_phase1_payload(
        selected_body_content=(
            "<html><body>"
            "<div>* ESP32-S3-BOX-3B Development Board.</div>"
            "<div>Quantity: 1</div>"
            "<div>Grand Total:</div>"
            "<div>50 USD</div>"
            "</body></html>"
        ),
    )

    result = scrubber.scrub(phase1)

    assert result.transactional_quality == "failed"
    assert result.scrub_status == "failed"
    assert "transactional_downgrade:missing_order_identifier_and_status" in result.scrub_diagnostics


@pytest.mark.asyncio
async def test_phase2_scrubber_end_to_end_from_real_phase1_fixture():
    payload = load_fixture("amazon_order_full.json")
    app = FastAPI()

    @app.get("/messages/{message_id}")
    async def get_message(message_id: str):
        assert message_id == "msg-order-1"
        return payload

    client = GmailMailboxClient(transport=ASGITransport(app=app))
    client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    full_message = await client.fetch_full_message_payload(token_record=token, message_id="msg-order-1")
    await client.aclose()

    phase1 = GmailOrderPhase1Processor().normalize_fetched_email(
        GmailOrderPhase1Processor().package_fetched_email(account_id="primary", payload=full_message)
    )
    scrubbed = GmailOrderPhase2Scrubber().scrub(phase1)

    assert scrubbed.schema_version == "gmail.phase2.scrubbed.v1"
    assert scrubbed.message_id == "msg-order-1"
    assert scrubbed.sender_domain == "amazon.com"
    assert scrubbed.selected_body_source == "parsed_mime_html_part"
    assert scrubbed.scrub_status == "partial"
    assert scrubbed.scrubbed_text
    assert "112-8876120-3805015" in scrubbed.scrubbed_text
    assert "Hello Dan," in scrubbed.scrubbed_text
    assert any("Order number" in line for line in scrubbed.normalized_lines)
    assert "Order number: 112-8876120-3805015" in scrubbed.scrubbed_text
    assert "Your Orders" not in scrubbed.scrubbed_text
    assert all("% off" not in line for line in scrubbed.normalized_lines)
    assert scrubbed.transactional_quality == "partial"
    assert scrubbed.scrub_metrics.input_char_count >= scrubbed.scrub_metrics.output_char_count
    assert scrubbed.scrub_metrics.reduction_ratio >= 0.0
    assert scrubbed.scrub_metrics.output_line_count == len([line for line in scrubbed.normalized_lines if line.strip()])
    assert scrubbed.normalization_metadata is not None
    payload_dump = scrubbed.model_dump()
    assert "raw_html" not in payload_dump["phase1_reference"]
    assert "transactional_targeting" in scrubbed.stage_statuses
    assert set(scrubbed.stage_statuses) == {
        "intake",
        "content_extraction",
        "transactional_targeting",
        "hidden_content",
        "chrome_removal",
        "footer_cutoff",
        "line_normalization",
        "link_extraction",
    }
