from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.message_store import GmailMessageStore
from providers.gmail.models import GmailOAuthConfig
from providers.gmail.models import GmailStoredMessage, GmailTrainingLabel
from providers.models import ProviderAccountRecord, ProviderId
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_send_user_notification_publishes_core_contract(config, core_client_factory):
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=mqtt_manager)
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"

    published = service.send_user_notification(
        title="Hexe Email warning",
        message="Something needs attention.",
        severity="warning",
        urgency="actions_needed",
        dedupe_key="test-warning",
        event_type="test_warning",
        summary="Test warning",
        source_component="tests",
        data={"scope": "unit"},
    )

    assert published is True
    assert len(mqtt_manager.notification_requests) == 1
    request = mqtt_manager.notification_requests[0]
    assert request.node_id == "node-1"
    assert request.kind == "event"
    assert request.targets.broadcast is True
    assert request.targets.external == ["ha"]
    assert request.delivery is not None
    assert request.delivery.severity == "warning"
    assert request.delivery.urgency == "actions_needed"
    assert request.delivery.dedupe_key == "test-warning"
    assert request.content is not None
    assert request.content.title == "Hexe Email warning"
    assert request.event is not None
    assert request.event.event_type == "test_warning"


@pytest.mark.asyncio
async def test_gmail_fetch_warning_and_recovery_notifications_are_transition_based(config, core_client_factory):
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=mqtt_manager)
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"

    GmailProviderConfigStore(config.runtime_dir).save(GmailOAuthConfig(enabled=True))

    await service._run_due_gmail_fetches()
    await service._run_due_gmail_fetches()

    assert len(mqtt_manager.notification_requests) == 1
    warning_request = mqtt_manager.notification_requests[0]
    assert warning_request.delivery is not None
    assert warning_request.delivery.severity == "warning"
    assert warning_request.content is not None
    assert "paused" in (warning_request.content.message or "").lower()

    adapter = service.provider_registry.get_provider("gmail")

    async def list_accounts():
        return [
            ProviderAccountRecord(
                provider_id=ProviderId.GMAIL,
                account_id="acct-1",
                status="connected",
            )
        ]

    async def gmail_fetch_messages(window: str, **kwargs):
        return {"window": window}

    adapter.list_accounts = list_accounts  # type: ignore[method-assign]
    service.gmail_fetch_messages = gmail_fetch_messages  # type: ignore[method-assign]

    await service._run_due_gmail_fetches()

    assert len(mqtt_manager.notification_requests) == 2
    recovery_request = mqtt_manager.notification_requests[1]
    assert recovery_request.delivery is not None
    assert recovery_request.delivery.severity == "success"
    assert recovery_request.content is not None
    assert "back online" in (recovery_request.content.title or "").lower()


def test_gmail_fetch_error_notification_uses_reusable_sender(config, core_client_factory):
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=mqtt_manager)
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"

    service._set_gmail_fetch_notification_state("error", "Gmail fetch scheduler failed: boom")

    assert len(mqtt_manager.notification_requests) == 1
    request = mqtt_manager.notification_requests[0]
    assert request.delivery is not None
    assert request.delivery.severity == "error"
    assert request.delivery.urgency == "urgent"
    assert request.content is not None
    assert "failed" in (request.content.message or "").lower()


@pytest.mark.asyncio
async def test_trust_activation_publishes_online_notification(core_client_factory, config):
    core_app = build_core_app()
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=mqtt_manager)

    await service.start()
    core_app.state.sessions["sx_123"]["status"] = "approved"
    await asyncio.sleep(0.05)
    await service.stop()

    assert mqtt_manager.notification_requests
    request = mqtt_manager.notification_requests[0]
    assert request.delivery is not None
    assert request.delivery.severity == "success"
    assert request.content is not None
    assert "online" in (request.content.title or "").lower()


@pytest.mark.asyncio
async def test_action_required_email_notification_is_reusable_and_marks_message(config, core_client_factory):
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=mqtt_manager)
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"

    store = GmailMessageStore(config.runtime_dir)
    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                subject="Please approve today",
                sender="Sender <sender@example.com>",
                received_at=datetime(2026, 4, 3, 10, 0, 0),
            )
        ]
    )

    sent = service._notify_for_new_email_classification(
        account_id="primary",
        message_id="msg-1",
        classification_label=GmailTrainingLabel.ACTION_REQUIRED,
        confidence=0.97,
        source_component="gmail_ai_classification",
    )

    assert sent is True
    assert len(mqtt_manager.notification_requests) == 1
    request = mqtt_manager.notification_requests[0]
    assert request.content is not None
    assert "Sender <sender@example.com>" in (request.content.message or "")
    assert "Please approve today" in (request.content.message or "")
    assert "0.97" in (request.content.message or "")
    assert store.has_notification_label("primary", "msg-1", GmailTrainingLabel.ACTION_REQUIRED.value) is True

    sent_again = service._notify_for_new_email_classification(
        account_id="primary",
        message_id="msg-1",
        classification_label=GmailTrainingLabel.ACTION_REQUIRED,
        confidence=0.97,
        source_component="gmail_ai_classification",
    )

    assert sent_again is False
    assert len(mqtt_manager.notification_requests) == 1


@pytest.mark.asyncio
async def test_order_email_notification_uses_order_flag(config, core_client_factory):
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=mqtt_manager)
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"

    store = GmailMessageStore(config.runtime_dir)
    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-2",
                subject="Your order has shipped",
                sender="Store <orders@example.com>",
                received_at=datetime(2026, 4, 3, 11, 0, 0),
            )
        ]
    )

    sent = service._notify_for_new_email_classification(
        account_id="primary",
        message_id="msg-2",
        classification_label=GmailTrainingLabel.ORDER,
        confidence=0.88,
        source_component="gmail_local_classification",
    )

    assert sent is True
    assert len(mqtt_manager.notification_requests) == 1
    request = mqtt_manager.notification_requests[0]
    assert request.content is not None
    assert "Your order has shipped" in (request.content.message or "")
    assert request.delivery is not None
    assert request.delivery.urgency == "notification"
    assert store.has_notification_label("primary", "msg-2", GmailTrainingLabel.ORDER.value) is True
