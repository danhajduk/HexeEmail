from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from providers.gmail.models import GmailActionItemState, GmailStoredMessage, GmailTrainingLabel
from service import NodeService


def _message(message_id: str, *, thread_id: str = "thread-1") -> GmailStoredMessage:
    return GmailStoredMessage(
        account_id="primary",
        message_id=message_id,
        thread_id=thread_id,
        subject="Please sign this document",
        sender="Sender <sender@example.com>",
        received_at=datetime(2026, 4, 29, 8, 30, 0).astimezone(),
        local_label=GmailTrainingLabel.ACTION_REQUIRED.value,
        local_label_confidence=0.93,
    )


def _pipeline_result(*, message_id: str, action_url: str | None, trust_level: str = "trusted") -> dict[str, object]:
    extracted_fields = {
        "document_id": {"field_name": "document_id", "value": "DOC-123", "is_valid": True},
        "due_date": {"field_name": "due_date", "value": "2026-04-30", "is_valid": True},
    }
    if action_url is not None:
        extracted_fields["action_url"] = {"field_name": "action_url", "value": action_url, "is_valid": True}
    record = {
        "schema_version": "shared-structured-output.v1",
        "flow_family": "action_required",
        "persisted_at": "2026-04-29T16:00:00Z",
        "trust_level": trust_level,
        "decision": "review_needed" if trust_level == "review_needed" else "accept",
        "decision_reason": "hard_validation_failure" if trust_level == "review_needed" else "accepted",
        "confidence": 0.84,
        "confidence_level": "high",
        "extraction_source": "active",
        "profile_id": "document_signature_required",
        "extracted_fields": extracted_fields,
        "diagnostics": ["decision:review_needed"] if trust_level == "review_needed" else [],
        "message_metadata": {"message_id": message_id, "account_id": "primary"},
    }
    phase7 = SimpleNamespace(record=SimpleNamespace(model_dump=lambda mode="json": record))
    phase4 = SimpleNamespace(profile_id="document_signature_required")
    return {"phase7": phase7, "phase4": phase4}


def test_action_required_sync_creates_and_groups_items(config):
    service = NodeService(config)
    adapter = service.provider_registry.get_provider("gmail")
    first = _message("msg-1")
    second = _message("msg-2", thread_id="thread-2")
    third = _message("msg-3")
    adapter.message_store.upsert_messages([first, second, third])

    service._sync_action_required_item_from_message(
        account_id="primary",
        message=first,
        pipeline_result=_pipeline_result(message_id="msg-1", action_url="https://example.com/action/123"),
        action_decision={"summary": "Sign the document.", "human_review_required": False},
    )
    service._sync_action_required_item_from_message(
        account_id="primary",
        message=second,
        pipeline_result=_pipeline_result(message_id="msg-2", action_url="https://example.com/action/123"),
        action_decision={"summary": "Same document reminder.", "human_review_required": False},
    )
    service._sync_action_required_item_from_message(
        account_id="primary",
        message=third,
        pipeline_result=_pipeline_result(message_id="msg-3", action_url=None),
        action_decision={"summary": "Same thread reminder.", "human_review_required": False},
    )

    items = adapter.action_item_store.list_items("primary")

    assert len(items) == 1
    item = items[0]
    assert item.state == GmailActionItemState.READY
    assert item.profile_id == "document_signature_required"
    assert item.confidence == 0.84
    assert item.group_key == "action_url:https://example.com/action/123"
    assert item.grouped_message_ids == ["msg-1", "msg-2", "msg-3"]
    assert item.ai_decision_payload is not None
    assert item.ai_decision_payload["summary"] == "Same thread reminder."


def test_action_required_sync_preserves_operator_state(config):
    service = NodeService(config)
    adapter = service.provider_registry.get_provider("gmail")
    message = _message("msg-1")
    adapter.message_store.upsert_messages([message])

    created = service._sync_action_required_item_from_message(
        account_id="primary",
        message=message,
        pipeline_result=_pipeline_result(message_id="msg-1", action_url="https://example.com/action/123"),
        action_decision={"summary": "Sign the document.", "human_review_required": False},
    )
    assert created is not None
    adapter.action_item_store.update_state("primary", created.item_id, GmailActionItemState.DONE)

    service._sync_action_required_item_from_message(
        account_id="primary",
        message=message,
        pipeline_result=_pipeline_result(
            message_id="msg-1",
            action_url="https://example.com/action/123",
            trust_level="review_needed",
        ),
        action_decision={"summary": "Sign the document.", "human_review_required": True},
    )

    loaded = adapter.action_item_store.get_item("primary", created.item_id)

    assert loaded is not None
    assert loaded.state == GmailActionItemState.DONE
    assert "ai_human_review_required" in loaded.review_reasons


@pytest.mark.asyncio
async def test_action_required_notification_syncs_item(config):
    service = NodeService(config)
    adapter = service.provider_registry.get_provider("gmail")
    message = _message("msg-1")
    adapter.message_store.upsert_messages([message])

    async def fake_flow(*, account_id, message):
        return _pipeline_result(message_id=message.message_id, action_url="https://example.com/action/123")

    async def fake_action_decision(*, account_id, message, classification_label):
        return {"summary": "Sign the document.", "human_review_required": False}

    service._run_action_required_phase1_flow = fake_flow  # type: ignore[method-assign]
    service._execute_email_action_decision_for_message = fake_action_decision  # type: ignore[method-assign]
    service.send_email_classification_notification = lambda **kwargs: False  # type: ignore[method-assign]

    sent = await service._notify_for_new_email_classification(
        account_id="primary",
        message_id="msg-1",
        classification_label=GmailTrainingLabel.ACTION_REQUIRED,
        confidence=0.93,
        source_component="test",
    )

    items = adapter.action_item_store.list_items("primary")

    assert sent is False
    assert len(items) == 1
    assert items[0].source_message_id == "msg-1"
