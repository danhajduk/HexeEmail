from __future__ import annotations

from datetime import datetime

from providers.gmail.message_store import GmailMessageStore
from providers.gmail.models import (
    GmailSenderReputationInputs,
    GmailSenderReputationRecord,
    GmailSpamhausCheck,
    GmailStoredMessage,
    GmailTrainingLabel,
)


def test_gmail_message_store_persists_messages(runtime_dir):
    store = GmailMessageStore(runtime_dir)

    inserted = store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                thread_id="thread-1",
                subject="Hello",
                sender="sender@example.com",
                recipients=["primary@example.com"],
                snippet="hello world",
                label_ids=["INBOX", "UNREAD"],
                received_at=datetime(2026, 4, 1, 12, 0, 0),
            )
        ],
        now=datetime(2026, 4, 2, 12, 0, 0),
    )

    assert inserted == 1
    assert store.count_messages("primary") == 1
    saved = store.list_messages("primary", limit=1)[0]
    assert saved.message_id == "msg-1"
    assert saved.subject == "Hello"
    assert saved.recipients == ["primary@example.com"]


def test_gmail_message_store_enforces_six_month_retention(runtime_dir):
    store = GmailMessageStore(runtime_dir)

    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="old-msg",
                received_at=datetime(2025, 9, 30, 8, 0, 0),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="fresh-msg",
                received_at=datetime(2026, 3, 31, 8, 0, 0),
            ),
        ],
        now=datetime(2026, 4, 2, 12, 0, 0),
    )

    messages = store.list_messages("primary", limit=10)
    assert [message.message_id for message in messages] == ["fresh-msg"]


def test_gmail_message_store_tracks_spamhaus_check_state(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Sender <sender@example.com>",
                received_at=datetime(2026, 4, 2, 12, 0, 0),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-2",
                sender="Another <another@example.com>",
                received_at=datetime(2026, 4, 2, 11, 0, 0),
            ),
        ],
        now=datetime(2026, 4, 2, 12, 30, 0),
    )

    pending_before = store.list_messages_pending_spamhaus("primary")
    store.upsert_spamhaus_check(
        GmailSpamhausCheck(
            account_id="primary",
            message_id="msg-1",
            sender_email="sender@example.com",
            sender_domain="example.com",
            checked=True,
            listed=True,
            status="listed",
        ),
        now=datetime(2026, 4, 2, 12, 45, 0),
    )
    summary = store.spamhaus_summary("primary")
    pending_after = store.list_messages_pending_spamhaus("primary")

    assert [message.message_id for message in pending_before] == ["msg-1", "msg-2"]
    assert summary.checked_count == 1
    assert summary.pending_count == 1
    assert summary.listed_count == 1
    assert [message.message_id for message in pending_after] == ["msg-2"]


def test_gmail_message_store_reports_checked_message_ids(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Sender <sender@example.com>",
                received_at=datetime(2026, 4, 2, 12, 0, 0),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-2",
                sender="Another <another@example.com>",
                received_at=datetime(2026, 4, 2, 11, 0, 0),
            ),
        ],
        now=datetime(2026, 4, 2, 12, 30, 0),
    )
    store.upsert_spamhaus_check(
        GmailSpamhausCheck(
            account_id="primary",
            message_id="msg-1",
            sender_email="sender@example.com",
            sender_domain="example.com",
            checked=True,
            listed=False,
            status="clean",
        ),
        now=datetime(2026, 4, 2, 12, 45, 0),
    )

    assert store.list_spamhaus_checked_message_ids("primary") == {"msg-1"}
    assert store.is_spamhaus_checked("primary", "msg-1") is True
    assert store.is_spamhaus_checked("primary", "msg-2") is False


def test_gmail_message_store_supports_local_training_labels(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Sender <sender@example.com>",
                received_at=datetime(2026, 4, 2, 12, 0, 0),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-2",
                sender="Another <another@example.com>",
                received_at=datetime(2026, 4, 2, 11, 0, 0),
                local_label="unknown",
                local_label_confidence=0.4,
            ),
        ],
        now=datetime(2026, 4, 2, 12, 30, 0),
    )

    store.update_local_classification(
        "primary",
        "msg-1",
        label=GmailTrainingLabel.DIRECT_HUMAN,
        confidence=0.95,
        manual_classification=True,
    )
    messages = store.list_messages("primary", limit=10)
    candidates = store.list_training_candidates("primary", limit=10, threshold=0.6)

    by_id = {message.message_id: message for message in messages}
    assert by_id["msg-1"].local_label == "direct_human"
    assert by_id["msg-1"].local_label_confidence == 0.95
    assert by_id["msg-1"].manual_classification is True
    assert [message.message_id for message in candidates] == ["msg-2"]


def test_gmail_message_store_tracks_notification_flags_per_label(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                subject="Review invoice",
                sender="Sender <sender@example.com>",
                received_at=datetime(2026, 4, 2, 12, 0, 0),
            )
        ],
        now=datetime(2026, 4, 2, 12, 30, 0),
    )

    assert store.has_notification_label("primary", "msg-1", GmailTrainingLabel.ACTION_REQUIRED.value) is False
    assert store.has_notification_label("primary", "msg-1", GmailTrainingLabel.ORDER.value) is False

    store.mark_notification_label_sent("primary", "msg-1", GmailTrainingLabel.ACTION_REQUIRED.value)

    assert store.has_notification_label("primary", "msg-1", GmailTrainingLabel.ACTION_REQUIRED.value) is True
    assert store.has_notification_label("primary", "msg-1", GmailTrainingLabel.ORDER.value) is False


def test_gmail_message_store_persists_sender_reputation_records(runtime_dir):
    store = GmailMessageStore(runtime_dir)

    saved = store.upsert_sender_reputation(
        GmailSenderReputationRecord(
            account_id="primary",
            entity_type="email",
            sender_value="alerts@example.com",
            sender_email="alerts@example.com",
            sender_domain="example.com",
            reputation_state="trusted",
            rating=3.5,
            inputs=GmailSenderReputationInputs(
                message_count=8,
                classification_positive_count=5,
                classification_negative_count=1,
                spamhaus_clean_count=2,
                spamhaus_listed_count=0,
            ),
            last_seen_at=datetime(2026, 4, 2, 12, 0, 0),
        ),
        now=datetime(2026, 4, 2, 12, 30, 0),
    )

    loaded = store.get_sender_reputation(
        "primary",
        entity_type="email",
        sender_value="alerts@example.com",
    )

    assert saved.updated_at == datetime(2026, 4, 2, 12, 30, 0)
    assert loaded is not None
    assert loaded.entity_type == "email"
    assert loaded.sender_domain == "example.com"
    assert loaded.reputation_state == "trusted"
    assert loaded.rating == 3.5
    assert loaded.inputs.message_count == 8
    assert loaded.inputs.classification_positive_count == 5
    assert loaded.inputs.spamhaus_clean_count == 2


def test_gmail_message_store_lists_sender_reputation_records_by_recency(runtime_dir):
    store = GmailMessageStore(runtime_dir)

    store.upsert_sender_reputation(
        GmailSenderReputationRecord(
            account_id="primary",
            entity_type="domain",
            sender_value="example.com",
            sender_domain="example.com",
            reputation_state="neutral",
            rating=0.5,
            inputs=GmailSenderReputationInputs(message_count=4),
        ),
        now=datetime(2026, 4, 2, 12, 0, 0),
    )
    store.upsert_sender_reputation(
        GmailSenderReputationRecord(
            account_id="primary",
            entity_type="email",
            sender_value="alerts@example.com",
            sender_email="alerts@example.com",
            sender_domain="example.com",
            reputation_state="risky",
            rating=-1.25,
            inputs=GmailSenderReputationInputs(
                message_count=2,
                spamhaus_listed_count=1,
            ),
        ),
        now=datetime(2026, 4, 2, 13, 0, 0),
    )

    all_records = store.list_sender_reputations("primary", limit=10)
    email_records = store.list_sender_reputations("primary", entity_type="email", limit=10)

    assert [record.sender_value for record in all_records] == ["alerts@example.com", "example.com"]
    assert [record.sender_value for record in email_records] == ["alerts@example.com"]
