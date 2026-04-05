from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from httpx import ASGITransport
import pytest

from providers.gmail.mailbox_client import GmailMailboxClient
from providers.gmail.models import GmailStoredMessage, GmailTokenRecord, GmailTrainingLabel
from providers.gmail.order_flow import GmailOrderPhase1Processor
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gmail_phase1"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def structured_fixture_payload(
    name: str,
    *,
    headers: dict[str, str],
    text_body: dict[str, object] | None = None,
    html_body: dict[str, object] | None = None,
) -> dict[str, object]:
    fixture = load_fixture(name)
    return {
        "message_id": fixture["id"],
        "thread_id": fixture.get("threadId"),
        "headers": headers,
        "text_body": text_body,
        "html_body": html_body,
        "fetch_status": "success",
    }


@pytest.mark.asyncio
async def test_gmail_mailbox_client_fetch_full_message_payload_preserves_raw_bodies_and_headers():
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

    assert full_message["message_id"] == "msg-order-1"
    assert full_message["subject"] == "Your Amazon order has been placed"
    assert full_message["sender"] == "Amazon Orders <auto-confirm@amazon.com>"
    assert full_message["headers"]["message-id"] == "<amazon-order-1@example.com>"
    assert full_message["text_body"]["content"].startswith("Hello Dan,")
    assert "<strong>ESP32-S3-BOX-3B</strong>" in full_message["html_body"]["content"]
    assert full_message["html_body"]["content_transfer_encoding"] == "7bit"
    assert full_message["fetch_status"] == "success"
    assert full_message["mime_parse_status"] == "success"
    assert "000000000000amazon" in full_message["mime_boundaries"]
    assert any(part["mime_type"] == "text/html" for part in full_message["part_inventory"])


def test_order_flow_normalizes_and_prefers_html():
    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(
        account_id="primary",
        payload=structured_fixture_payload(
            "amazon_order_full.json",
            headers={
                "from": "Amazon Orders <auto-confirm@amazon.com>",
                "subject": "Your Amazon order has been placed",
                "date": "Wed, 02 Apr 2026 10:00:00 -0700",
                "message-id": "<amazon-order-1@example.com>",
            },
            text_body={
                "content": "Hello Dan,\nThanks ordering the ESP32-S3-BOX-3B.\nOrder number: 112-8876120-3805015",
                "headers": {
                    "content-transfer-encoding": "7bit",
                    "content-type": "text/plain; charset=UTF-8",
                },
            },
            html_body={
                "content": "<div><p>Hello Dan,</p><p>Thanks ordering the <strong>ESP32-S3-BOX-3B</strong>.</p><p>Order number: 112-8876120-3805015</p></div>",
                "headers": {
                    "content-transfer-encoding": "7bit",
                    "content-type": "text/html; charset=UTF-8",
                },
            },
        ),
    )

    normalized = processor.normalize_fetched_email(fetched)

    assert normalized.sender_name == "Amazon Orders"
    assert normalized.sender_email == "auto-confirm@amazon.com"
    assert normalized.sender_domain == "amazon.com"
    assert normalized.raw_html is not None
    assert normalized.raw_text is not None
    assert normalized.decode_state.status == "success"
    assert normalized.sender_normalization_status == "success"
    assert normalized.selected_body_type == "html"
    assert normalized.selected_body_content == normalized.decoded_html
    assert normalized.selected_body_quality == "rich_html"
    assert normalized.decoded_html_quality == "rich_html"
    assert normalized.decoded_text_quality == "usable_text"
    assert normalized.body_selection_status == "success"
    assert normalized.selected_body_source == "parsed_mime_html_part"
    assert normalized.selected_body_selection_path == "quality_comparison"
    assert normalized.handoff_ready is True
    assert normalized.validation_status == "success"
    assert normalized.provider_message_id == fetched.message_id
    assert normalized.rfc_message_id == "<amazon-order-1@example.com>"
    assert normalized.mime_parts == normalized.part_inventory
    assert normalized.raw_html_hash is not None
    assert normalized.selected_body_hash is not None


def test_order_flow_decodes_quoted_printable_text():
    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(
        account_id="primary",
        payload=structured_fixture_payload(
            "quoted_printable_order.json",
            headers={
                "from": "Store Orders <orders@example.com>",
                "subject": "Order details",
                "date": "Wed, 02 Apr 2026 11:00:00 -0700",
                "message-id": "<qp-order@example.com>",
            },
            text_body={
                "content": "Hello Dan,=\nYour order total is =2434.99 and code =3D READY.",
                "headers": {
                    "content-transfer-encoding": "quoted-printable",
                    "content-type": "text/plain; charset=UTF-8",
                },
            },
        ),
    )

    normalized = processor.normalize_fetched_email(fetched)

    assert normalized.raw_text == "Hello Dan,=\nYour order total is =2434.99 and code =3D READY."
    assert normalized.decoded_text == "Hello Dan,Your order total is $34.99 and code = READY."
    assert normalized.decode_state.status == "success"
    assert normalized.selected_body_type == "text"
    assert normalized.selected_body_quality == "usable_text"
    assert normalized.selected_body_source == "parsed_mime_text_part"


def test_order_flow_does_not_false_decode_html_equals_sequences():
    processor = GmailOrderPhase1Processor()

    decoded, diagnostics = processor.decode_body(
        '<meta http-equiv="X-UA-Compatible" content="IE=edge"><meta name="viewport" content="width=device-width">',
        transfer_encoding="7bit",
        charset="utf-8",
    )

    assert decoded == '<meta http-equiv="X-UA-Compatible" content="IE=edge"><meta name="viewport" content="width=device-width">'
    assert diagnostics == []


def test_order_flow_respects_mime_charset_when_decoding():
    processor = GmailOrderPhase1Processor()

    decoded, diagnostics = processor.decode_body(
        "caf=E9 order ready",
        transfer_encoding="quoted-printable",
        charset="iso-8859-1",
    )

    assert decoded == "café order ready"
    assert all("failed:" not in item for item in diagnostics)


def test_order_flow_falls_back_to_text_when_html_missing():
    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(
        account_id="primary",
        payload=structured_fixture_payload(
            "missing_html_order.json",
            headers={
                "from": "Pickup Desk <orders@pickup.example.com>",
                "subject": "Your order is ready",
                "date": "Wed, 02 Apr 2026 12:00:00 -0700",
                "message-id": "<text-only-order@example.com>",
            },
            text_body={
                "content": "Your order is ready for pickup.",
                "headers": {
                    "content-transfer-encoding": "7bit",
                    "content-type": "text/plain; charset=UTF-8",
                },
            },
            html_body=None,
        ),
    )

    normalized = processor.normalize_fetched_email(fetched)

    assert normalized.selected_body_type == "text"
    assert normalized.selected_body_content == "Your order is ready for pickup."
    assert normalized.selected_body_quality == "fallback_text"
    assert normalized.decoded_text_quality == "fallback_text"
    assert normalized.body_availability.text_available is True
    assert normalized.body_availability.html_available is False


def test_order_flow_handles_malformed_sender_gracefully():
    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(
        account_id="primary",
        payload=structured_fixture_payload(
            "malformed_sender_order.json",
            headers={
                "from": "Amazon Marketplace Notifications",
                "subject": "Marketplace order update",
                "date": "Wed, 02 Apr 2026 13:00:00 -0700",
                "message-id": "<malformed-sender-order@example.com>",
            },
            text_body={
                "content": "Marketplace order update.",
                "headers": {
                    "content-transfer-encoding": "7bit",
                    "content-type": "text/plain; charset=UTF-8",
                },
            },
        ),
    )

    normalized = processor.normalize_fetched_email(fetched)

    assert normalized.sender_name == "Amazon Marketplace Notifications"
    assert normalized.sender_email is None
    assert normalized.sender_domain is None
    assert normalized.sender_normalization_status == "partial"
    assert normalized.validation_status == "partial"
    assert "sender_domain is required" in normalized.validation_diagnostics


def test_order_flow_normalizes_bare_email_sender():
    processor = GmailOrderPhase1Processor()

    sender = processor.normalize_sender("shipment-tracking@amazon.com")

    assert sender.sender_name is None
    assert sender.sender_email == "shipment-tracking@amazon.com"
    assert sender.sender_domain == "amazon.com"


def test_order_flow_marks_missing_body_without_crashing():
    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(
        account_id="primary",
        payload={
            "message_id": "missing-body-1",
            "headers": {
                "from": "Orders <orders@example.com>",
                "subject": "Missing body",
            },
            "fetch_status": "missing_body",
            "fetch_error": "gmail full message did not include text/plain or text/html body parts",
        },
    )

    normalized = processor.normalize_fetched_email(fetched)

    assert normalized.fetch_status == "partial"
    assert normalized.fetch_error == "gmail full message did not include text/plain or text/html body parts"
    assert normalized.selected_body_type == "none"
    assert normalized.selected_body_content is None
    assert normalized.body_selection_status == "failed"
    assert normalized.handoff_ready is False
    assert normalized.validation_status == "partial"
    assert "selected_body_content is required" in normalized.validation_diagnostics


def test_order_flow_populates_mime_inventory_and_boundaries():
    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(
        account_id="primary",
        payload={
            "message_id": "mime-1",
            "headers": {
                "from": "Orders <orders@example.com>",
                "subject": "Mime inventory",
            },
            "text_body": {
                "content": "plain body",
                "headers": {
                    "content-transfer-encoding": "7bit",
                    "content-type": "text/plain; charset=UTF-8",
                },
                "charset": "UTF-8",
                "mime_boundary": "inner-1",
            },
            "html_body": {
                "content": "<div>html body</div>",
                "headers": {
                    "content-transfer-encoding": "7bit",
                    "content-type": "text/html; charset=UTF-8",
                },
                "charset": "UTF-8",
                "mime_boundary": "inner-2",
            },
            "mime_parse_status": "success",
            "mime_diagnostics": [],
            "mime_boundaries": ["outer-1"],
            "part_inventory": [
                {"index": "0", "mime_type": "multipart/alternative"},
                {"index": "0.0", "mime_type": "text/plain"},
                {"index": "0.1", "mime_type": "text/html"},
            ],
            "fetch_status": "success",
        },
    )

    normalized = processor.normalize_fetched_email(fetched)

    assert normalized.mime_parse_status == "success"
    assert normalized.mime_boundaries == ["outer-1", "inner-2", "inner-1"]
    assert normalized.mime_parts == normalized.part_inventory
    assert len(normalized.part_inventory) == 3


def test_order_flow_hashes_are_deterministic():
    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(
        account_id="primary",
        payload={
            "message_id": "hash-1",
            "headers": {
                "from": "Orders <orders@example.com>",
                "subject": "Hash test",
            },
            "text_body": {
                "content": "Your order is ready for pickup with code 1234.",
                "headers": {
                    "content-transfer-encoding": "7bit",
                    "content-type": "text/plain; charset=UTF-8",
                },
            },
            "fetch_status": "success",
        },
    )

    normalized_a = processor.normalize_fetched_email(fetched)
    normalized_b = processor.normalize_fetched_email(fetched)

    assert normalized_a.raw_text_hash == normalized_b.raw_text_hash
    assert normalized_a.decoded_text_hash == normalized_b.decoded_text_hash
    assert normalized_a.selected_body_hash == normalized_b.selected_body_hash


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_name", "message_id", "expected_subject", "expected_body_type", "expected_handoff_ready"),
    [
        ("amazon_order_full.json", "msg-order-1", "Your Amazon order has been placed", "html", True),
        ("quoted_printable_order.json", "msg-qp-order", "Order details", "text", True),
        ("missing_html_order.json", "msg-text-order", "Your order is ready", "text", True),
        ("malformed_sender_order.json", "msg-malformed-order", "Marketplace order update", "text", False),
    ],
)
async def test_order_flow_end_to_end_real_fixtures(
    fixture_name: str,
    message_id: str,
    expected_subject: str,
    expected_body_type: str,
    expected_handoff_ready: bool,
):
    payload = load_fixture(fixture_name)
    app = FastAPI()

    @app.get("/messages/{requested_message_id}")
    async def get_message(requested_message_id: str):
        assert requested_message_id == message_id
        return payload

    client = GmailMailboxClient(transport=ASGITransport(app=app))
    client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    full_message = await client.fetch_full_message_payload(token_record=token, message_id=message_id)
    await client.aclose()

    processor = GmailOrderPhase1Processor()
    fetched = processor.package_fetched_email(account_id="primary", payload=full_message)
    normalized = processor.normalize_fetched_email(fetched)
    provider_message_id = str(full_message["message_id"])

    assert normalized.schema_version == "gmail.phase1.normalized.v1"
    assert normalized.provider == "gmail"
    assert normalized.message_id == provider_message_id
    assert normalized.provider_message_id == provider_message_id
    assert normalized.subject == expected_subject
    assert normalized.selected_body_type == expected_body_type
    assert normalized.selected_body_content
    assert normalized.normalization_metadata is not None
    assert normalized.normalization_metadata.normalizer_version == "order-phase1-normalizer.v2"
    assert set(normalized.stage_diagnostics) == {
        "fetch",
        "mime_parse",
        "sender_normalization",
        "decode",
        "body_selection",
        "validation",
    }
    assert all(
        "\ufffd" not in (value or "")
        for value in [normalized.decoded_html, normalized.decoded_text, normalized.selected_body_content]
    )
    assert normalized.handoff_ready is expected_handoff_ready


@pytest.mark.asyncio
async def test_order_flow_runs_from_order_classification_hook(config, core_client_factory, monkeypatch):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="order-hook-1",
                subject="Order hook",
                sender="Orders <orders@example.com>",
                recipients=["primary@example.com"],
                snippet="hook me",
                received_at=datetime.now().astimezone(),
                local_label="order",
                local_label_confidence=0.99,
            )
        ]
    )
    calls: list[tuple[str, str]] = []

    async def fake_fetch_and_normalize_message(*, fetch_full_message_payload, account_id: str, message_id: str):
        del fetch_full_message_payload
        calls.append((account_id, message_id))
        return processor.normalize_fetched_email(
            processor.package_fetched_email(
                account_id=account_id,
                payload={
                    "message_id": message_id,
                    "headers": {"from": "Orders <orders@example.com>", "subject": "Order hook"},
                    "text_body": {"content": "order hook", "headers": {}},
                    "fetch_status": "ok",
                },
            )
        )

    processor = GmailOrderPhase1Processor()
    monkeypatch.setattr(service.gmail_order_flow, "fetch_and_normalize_message", fake_fetch_and_normalize_message)

    async def fake_action_decision(**kwargs):
        del kwargs
        return None

    monkeypatch.setattr(service, "_execute_email_action_decision_for_message", fake_action_decision)
    monkeypatch.setattr(service, "send_email_classification_notification", lambda **kwargs: False)

    await service._notify_for_new_email_classification(
        account_id="primary",
        message_id="order-hook-1",
        classification_label=GmailTrainingLabel.ORDER,
        confidence=0.99,
        source_component="test_order_hook",
    )

    await service.stop()

    assert calls == [("primary", "order-hook-1")]
