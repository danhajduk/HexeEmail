from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from providers.gmail.action_item_store import GmailActionItemStore
from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.models import GmailActionItem, GmailActionItemState


def test_gmail_action_item_store_persists_action_item(runtime_dir):
    store = GmailActionItemStore(runtime_dir)
    now = datetime(2026, 4, 29, 9, 30, 0).astimezone()
    item = GmailActionItem(
        account_id="primary",
        item_id="action:msg-1",
        group_key="thread:thread-1",
        source_message_id="msg-1",
        thread_id="thread-1",
        sender="Billing <billing@example.com>",
        subject="Payment due",
        received_at=datetime(2026, 4, 29, 8, 30, 0).astimezone(),
        state=GmailActionItemState.REVIEW_NEEDED,
        profile_id="payment_due",
        profile_type="payment_due",
        extracted_fields={"amount": "$12.00", "due_date": "2026-04-30"},
        flow_output={"decision": "review_needed"},
        ai_decision_payload={"summary": "Pay by tomorrow", "human_review_required": True},
        confidence=0.83,
        priority_score=72.5,
        priority_inputs={"profile_score": 58, "deadline_score": 14},
        snoozed_until=now + timedelta(hours=2),
        reminder_at=now + timedelta(hours=1),
        operator_note="Check account first",
        grouped_message_ids=["msg-1", "msg-2"],
        review_reasons=["missing_action_url"],
    )

    saved = store.upsert_item(item, now=now)
    loaded = store.get_item("primary", "action:msg-1")

    assert saved.created_at == now
    assert loaded is not None
    assert loaded.state == GmailActionItemState.REVIEW_NEEDED
    assert loaded.profile_id == "payment_due"
    assert loaded.extracted_fields["amount"] == "$12.00"
    assert loaded.ai_decision_payload is not None
    assert loaded.ai_decision_payload["summary"] == "Pay by tomorrow"
    assert loaded.priority_score == 72.5
    assert loaded.priority_inputs["profile_score"] == 58
    assert loaded.grouped_message_ids == ["msg-1", "msg-2"]
    assert loaded.review_reasons == ["missing_action_url"]
    assert store.count_items("primary") == 1


def test_gmail_action_item_store_updates_state_and_preserves_created_at(runtime_dir):
    store = GmailActionItemStore(runtime_dir)
    created_at = datetime(2026, 4, 29, 9, 30, 0).astimezone()
    updated_at = datetime(2026, 4, 29, 10, 0, 0).astimezone()
    store.upsert_item(
        GmailActionItem(
            account_id="primary",
            item_id="action:msg-1",
            source_message_id="msg-1",
            sender="sender@example.com",
            subject="Please review",
            received_at=datetime(2026, 4, 29, 8, 30, 0).astimezone(),
            priority_score=10,
        ),
        now=created_at,
    )

    updated = store.update_state("primary", "action:msg-1", GmailActionItemState.DONE, now=updated_at)

    assert updated is not None
    assert updated.state == GmailActionItemState.DONE
    assert updated.created_at == created_at
    assert updated.updated_at == updated_at
    assert updated.state_updated_at == updated_at


def test_gmail_action_item_store_finds_item_by_group_key(runtime_dir):
    store = GmailActionItemStore(runtime_dir)
    now = datetime(2026, 4, 29, 9, 30, 0).astimezone()
    store.upsert_item(
        GmailActionItem(
            account_id="primary",
            item_id="action:msg-1",
            group_key="action_url:https://example.com/action",
            source_message_id="msg-1",
            received_at=now,
        ),
        now=now,
    )

    loaded = store.get_item_by_group_key("primary", "action_url:https://example.com/action")

    assert loaded is not None
    assert loaded.item_id == "action:msg-1"


def test_gmail_action_item_store_lists_by_state_oldest_first(runtime_dir):
    store = GmailActionItemStore(runtime_dir)
    now = datetime(2026, 4, 29, 9, 30, 0).astimezone()
    for item_id, state, priority, received_at in [
        ("action:newer", GmailActionItemState.NEW, 90, now),
        ("action:older", GmailActionItemState.NEW, 20, now - timedelta(hours=2)),
        ("action:done", GmailActionItemState.DONE, 100, now - timedelta(hours=3)),
    ]:
        store.upsert_item(
            GmailActionItem(
                account_id="primary",
                item_id=item_id,
                source_message_id=item_id,
                received_at=received_at,
                state=state,
                priority_score=priority,
            ),
            now=now,
        )

    active = store.list_items("primary", states=[GmailActionItemState.NEW])

    assert [item.item_id for item in active] == ["action:older", "action:newer"]


def test_gmail_action_item_store_validates_score_and_confidence():
    with pytest.raises(ValueError):
        GmailActionItem(
            account_id="primary",
            item_id="action:bad",
            source_message_id="msg-1",
            received_at=datetime(2026, 4, 29, 8, 30, 0).astimezone(),
            priority_score=101,
        )
    with pytest.raises(ValueError):
        GmailActionItem(
            account_id="primary",
            item_id="action:bad-confidence",
            source_message_id="msg-1",
            received_at=datetime(2026, 4, 29, 8, 30, 0).astimezone(),
            confidence=1.1,
        )


def test_gmail_provider_adapter_owns_action_item_store(runtime_dir):
    adapter = GmailProviderAdapter(runtime_dir)

    assert isinstance(adapter.action_item_store, GmailActionItemStore)
    assert adapter.action_item_store.path.exists()
