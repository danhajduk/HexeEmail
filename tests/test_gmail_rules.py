from __future__ import annotations

from datetime import datetime

import pytest

from config import AppConfig
from providers.gmail.models import GmailRulesInput, GmailStoredMessage, GmailTrainingLabel
from providers.gmail.rules import (
    full_html_required,
    matching_label_override,
    normalize_full_html_rules,
    normalize_label_override_rules,
)
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


def test_gmail_sender_rules_match_domains_and_senders():
    label_rules = normalize_label_override_rules(
        [
            {"match_type": "domain", "value": "parcelpending.com", "label": "action_required"},
            {"match_type": "sender", "value": "orders@example.com", "label": "order"},
        ]
    )
    full_html_rules = normalize_full_html_rules(
        [
            {"match_type": "domain", "value": "visionworks.com"},
        ]
    )
    parcelpending_message = GmailStoredMessage(
        account_id="primary",
        message_id="msg-1",
        sender="Parcel Pending <notice@mail.parcelpending.com>",
        received_at=datetime(2026, 4, 29, 8, 0, 0).astimezone(),
    )
    visionworks_message = GmailStoredMessage(
        account_id="primary",
        message_id="msg-2",
        sender="Visionworks <visionworks@c.visionworks.com>",
        received_at=datetime(2026, 4, 29, 8, 0, 0).astimezone(),
    )

    matched_rule = matching_label_override(label_rules, parcelpending_message)

    assert matched_rule is not None
    assert matched_rule.label == GmailTrainingLabel.ACTION_REQUIRED
    assert full_html_rules[0].value == "visionworks.com"
    assert full_html_rules[0].enabled is True
    assert full_html_required(full_html_rules, visionworks_message)
    assert matching_label_override(label_rules, visionworks_message) is None


@pytest.mark.asyncio
async def test_gmail_label_override_classifies_before_local_model(runtime_dir, core_client_factory):
    config = AppConfig(
        CORE_BASE_URL="http://core.test",
        NODE_NAME="node-test",
        NODE_TYPE="email-node",
        NODE_SOFTWARE_VERSION="0.1.0",
        NODE_NONCE="nonce-test",
        RUNTIME_DIR=runtime_dir,
        API_PORT=9003,
        UI_PORT=8083,
        GMAIL_STATUS_POLL_ON_STARTUP=False,
        GMAIL_FETCH_POLL_ON_STARTUP=False,
    )
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="parcel-1",
                sender="Parcel Pending <notice@parcelpending.com>",
                subject="Package ready",
                received_at=datetime(2026, 4, 29, 8, 0, 0).astimezone(),
            )
        ]
    )
    await service.update_gmail_rules(
        GmailRulesInput(
            label_overrides=[
                {"match_type": "domain", "value": "parcelpending.com", "label": GmailTrainingLabel.ACTION_REQUIRED}
            ],
            full_html_required=[],
        ),
        account_id="primary",
    )

    try:
        local_processed, ai_candidates = await service._classify_candidates_locally(
            account_id="primary",
            candidates=adapter.message_store.list_messages("primary"),
        )
    finally:
        await service.stop()

    classified = adapter.message_store.list_messages("primary")[0]
    assert local_processed == 1
    assert ai_candidates == []
    assert classified.local_label == GmailTrainingLabel.ACTION_REQUIRED.value
    assert classified.local_label_confidence == 1.0
