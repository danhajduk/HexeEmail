from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app
from providers.gmail.models import GmailActionItem, GmailActionItemState, GmailStoredMessage, GmailTrainingLabel
from service import NodeService
from tests.helpers import FakeMQTTManager


def _seed_action_item(service: NodeService) -> str:
    adapter = service.provider_registry.get_provider("gmail")
    received_at = datetime(2026, 4, 29, 8, 30, 0).astimezone()
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-action-1",
                thread_id="thread-action-1",
                subject="Please sign",
                sender="Sender <sender@example.com>",
                recipients=["user@example.com"],
                snippet="Please sign this document.",
                label_ids=["INBOX"],
                received_at=received_at,
                raw_payload='{"body":"Please sign this document."}',
            )
        ]
    )
    item = adapter.action_item_store.upsert_item(
        GmailActionItem(
            account_id="primary",
            item_id="action:test-1",
            group_key="action_url:https://example.com/sign",
            source_message_id="msg-action-1",
            thread_id="thread-action-1",
            sender="Sender <sender@example.com>",
            subject="Please sign",
            received_at=received_at,
            state=GmailActionItemState.REVIEW_NEEDED,
            profile_id="document_signature_required",
            profile_type="document_signature_required",
            extracted_fields={
                "action_url": {"value": "https://example.com/sign"},
                "due_date": {"value": "2026-04-30"},
            },
            flow_output={"trust_level": "review_needed", "decision": "review_needed"},
            ai_decision_payload={"summary": "Sign the document.", "human_review_required": True},
            confidence=0.82,
            priority_score=80,
            grouped_message_ids=["msg-action-1", "msg-action-2"],
            review_reasons=["ai_human_review_required"],
        )
    )
    return item.item_id


@pytest.mark.asyncio
async def test_action_required_api_hides_future_snoozed_items_by_default(config):
    service = NodeService(config, mqtt_manager=FakeMQTTManager())
    item_id = _seed_action_item(service)
    app = create_app(config=config, service=service)
    snooze_until = (datetime.now().astimezone() + timedelta(days=1)).isoformat()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        snooze_response = await client.patch(
            f"/api/actions/{item_id}/snooze",
            json={"snoozed_until": snooze_until, "reminder_at": snooze_until},
        )
        default_list_response = await client.get("/api/actions")
        snoozed_list_response = await client.get("/api/actions", params={"states": "snoozed"})

    assert snooze_response.status_code == 200
    assert default_list_response.status_code == 200
    assert default_list_response.json()["count"] == 0
    assert snoozed_list_response.status_code == 200
    assert snoozed_list_response.json()["count"] == 1


@pytest.mark.asyncio
async def test_action_required_api_lists_details_and_updates_items(config):
    service = NodeService(config, mqtt_manager=FakeMQTTManager())
    item_id = _seed_action_item(service)
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_response = await client.get("/api/actions", params={"states": "review_needed", "high_priority": True})
        detail_response = await client.get(f"/api/actions/{item_id}")
        state_response = await client.patch(f"/api/actions/{item_id}/state", json={"state": "ready"})
        note_response = await client.patch(f"/api/actions/{item_id}/note", json={"operator_note": " reviewed by me "})
        snooze_until = (datetime(2026, 4, 29, 12, 0, 0).astimezone()).isoformat()
        reminder_at = (datetime(2026, 4, 29, 11, 0, 0).astimezone()).isoformat()
        snooze_response = await client.patch(
            f"/api/actions/{item_id}/snooze",
            json={"snoozed_until": snooze_until, "reminder_at": reminder_at},
        )

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["count"] == 1
    assert list_body["items"][0]["item_id"] == item_id
    assert list_body["items"][0]["action_url"] == "https://example.com/sign"
    assert list_body["items"][0]["due_at"].startswith("2026-04-30")
    assert list_body["items"][0]["grouped_message_count"] == 2

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["source_message"]["message_id"] == "msg-action-1"
    assert detail_body["extracted_fields"]["action_url"]["value"] == "https://example.com/sign"
    assert detail_body["ai_decision_payload"]["summary"] == "Sign the document."

    assert state_response.status_code == 200
    assert state_response.json()["state"] == "ready"
    assert note_response.status_code == 200
    assert note_response.json()["operator_note"] == "reviewed by me"
    assert snooze_response.status_code == 200
    assert snooze_response.json()["state"] == "snoozed"
    assert snooze_response.json()["reminder_at"] == reminder_at


@pytest.mark.asyncio
async def test_action_required_api_reclassifies_grouped_messages(config):
    service = NodeService(config, mqtt_manager=FakeMQTTManager())
    item_id = _seed_action_item(service)
    adapter = service.provider_registry.get_provider("gmail")
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-action-2",
                thread_id="thread-action-1",
                subject="Please sign follow-up",
                sender="Sender <sender@example.com>",
                recipients=["user@example.com"],
                snippet="Reminder to sign.",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 29, 9, 30, 0).astimezone(),
                raw_payload='{"body":"Reminder to sign."}',
            )
        ]
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/actions/{item_id}/classification",
            json={"label": "system", "confidence": 0.88},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "ignored"
    assert body["reclassification"]["label"] == "system"
    assert body["reclassification"]["message_ids"] == ["msg-action-1", "msg-action-2"]
    for message_id in ("msg-action-1", "msg-action-2"):
        message = adapter.message_store.get_message("primary", message_id)
        assert message is not None
        assert message.local_label == GmailTrainingLabel.SYSTEM.value
        assert message.local_label_confidence == 0.88
        assert message.manual_classification is True


@pytest.mark.asyncio
async def test_action_required_api_resends_notification(config):
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, mqtt_manager=mqtt_manager)
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"
    item_id = _seed_action_item(service)
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/actions/{item_id}/notify")

    assert response.status_code == 200
    body = response.json()
    assert body["notification"]["sent"] is True
    assert len(mqtt_manager.notification_requests) == 1
    request = mqtt_manager.notification_requests[0]
    assert request.event is not None
    assert request.event.event_type == "gmail_action_required_email"
    assert request.delivery is not None
    assert request.delivery.dedupe_key is not None
    assert request.delivery.dedupe_key.startswith("action-item-manual-notify:primary:action:test-1:")


@pytest.mark.asyncio
async def test_action_required_due_reminder_wakes_snooze_and_sends_once(config):
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, mqtt_manager=mqtt_manager)
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"
    item_id = _seed_action_item(service)
    adapter = service.provider_registry.get_provider("gmail")
    item = adapter.action_item_store.get_item("primary", item_id)
    assert item is not None
    now = datetime(2026, 4, 29, 12, 0, 0).astimezone()
    adapter.action_item_store.upsert_item(
        item.model_copy(
            update={
                "state": GmailActionItemState.SNOOZED,
                "snoozed_until": now - timedelta(minutes=5),
                "reminder_at": now - timedelta(minutes=1),
                "reminder_sent_at": None,
            }
        )
    )

    result = await service.process_due_action_item_reminders(now=now)
    second_result = await service.process_due_action_item_reminders(now=now + timedelta(minutes=5))
    loaded = adapter.action_item_store.get_item("primary", item_id)

    assert result["woken"] == 1
    assert result["sent"] == 1
    assert second_result["sent"] == 0
    assert loaded is not None
    assert loaded.state == GmailActionItemState.READY
    assert loaded.reminder_sent_at is not None
    assert len(mqtt_manager.notification_requests) == 1
    assert mqtt_manager.notification_requests[0].event is not None
    assert mqtt_manager.notification_requests[0].event.event_type == "action_required_reminder"


@pytest.mark.asyncio
async def test_action_required_api_regenerates_ai_decision(config):
    service = NodeService(config, mqtt_manager=FakeMQTTManager())
    item_id = _seed_action_item(service)

    async def fake_action_decision(*, account_id, message, classification_label):
        return {"summary": "Fresh decision.", "human_review_required": False}

    service._execute_email_action_decision_for_message = fake_action_decision  # type: ignore[method-assign]
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/actions/{item_id}/regenerate-ai-decision")

    assert response.status_code == 200
    body = response.json()
    assert body["ai_decision_payload"]["summary"] == "Fresh decision."
    assert body["source_message"]["message_id"] == "msg-action-1"
