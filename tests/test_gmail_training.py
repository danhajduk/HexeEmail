from __future__ import annotations

from datetime import datetime

from providers.gmail.models import GmailStoredMessage, GmailTrainingLabel
from providers.gmail.training import (
    NORMALIZATION_VERSION,
    build_training_dataset,
    flatten_message,
    is_trainable_message,
    parse_label_ids,
    render_flat_training_text,
    render_raw_training_text,
)


def test_gmail_training_normalization_renders_expected_flat_text():
    message = GmailStoredMessage(
        account_id="primary",
        message_id="msg-1",
        sender='Hotels.com <MAIL@EG.HOTELS.COM>',
        recipients=["primary@example.com"],
        subject="Re: FWD: Your Order!!!",
        snippet="Click here: https://example.com\n> old reply\nSent from my iPhone\nOrder #12345 ships tomorrow",
        label_ids=["INBOX", "UNREAD"],
        received_at=datetime(2026, 4, 2, 12, 0, 0),
        raw_payload='{"payload":{"headers":[{"name":"To","value":"primary@example.com"},{"name":"Cc","value":"friend@example.com"},{"name":"List-Unsubscribe","value":"<mailto:stop@example.com>"}]}}',
    )

    flattened = flatten_message(message, account_email="primary@example.com")
    rendered = render_flat_training_text(flattened)

    assert flattened.sender_email == "mail@eg.hotels.com"
    assert flattened.sender_domain == "eg.hotels.com"
    assert flattened.recipient_flags.to_me_only is False
    assert flattened.recipient_flags.cc_me is False
    assert flattened.recipient_flags.recipient_count == "rc_2_3"
    assert flattened.subject == "your order"
    assert flattened.flags.has_unsubscribe is True
    assert flattened.body_preview == "click here url order number ships tomorrow"
    assert rendered == "\n".join(
        [
            "from: mail@eg.hotels.com",
            "domain: eg.hotels.com",
            "recipient_flags: to_me_only=false cc_me=false recipient_count=rc_2_3",
            "subject: your order",
            "flags: has_attachment=false is_reply=true is_forward=false has_unsubscribe=true",
            "body: click here url order number ships tomorrow",
        ]
    )


def test_gmail_training_normalization_version_is_explicit():
    assert NORMALIZATION_VERSION == "v2"


def test_gmail_training_raw_render_preserves_human_readable_text():
    message = GmailStoredMessage(
        account_id="primary",
        message_id="msg-2",
        sender="Alerts <alerts@example.com>",
        recipients=["primary@example.com"],
        subject="Look who&#39;s checking you out",
        snippet="<div>Tap now</div>",
        label_ids=["INBOX", "UNREAD"],
        received_at=datetime(2026, 4, 2, 12, 0, 0),
    )

    rendered = render_raw_training_text(message)

    assert "subject: Look who's checking you out" in rendered
    assert "body: Tap now" in rendered


def test_gmail_training_parses_labels_and_excludes_non_trainable_mailboxes():
    assert parse_label_ids("INBOX\nUNREAD\nSENT") == {"INBOX", "UNREAD", "SENT"}
    assert is_trainable_message(
        GmailStoredMessage(
            account_id="primary",
            message_id="sent-1",
            label_ids=["SENT", "INBOX"],
            received_at=datetime(2026, 4, 2, 12, 0, 0),
        )
    ) is False


def test_gmail_training_builds_weighted_dataset_with_manual_local_and_bootstrap_sources():
    messages = [
        GmailStoredMessage(
            account_id="primary",
            message_id="manual-1",
            sender="Person <person@example.com>",
            recipients=["primary@example.com"],
            subject="Please review this",
            snippet="Can you take a look?",
            label_ids=["CATEGORY_PERSONAL", "INBOX"],
            received_at=datetime(2026, 4, 2, 12, 0, 0),
            local_label="direct_human",
            local_label_confidence=1.0,
            manual_classification=True,
        ),
        GmailStoredMessage(
            account_id="primary",
            message_id="local-1",
            sender="Billing <billing@example.com>",
            recipients=["primary@example.com"],
            subject="Statement ready",
            snippet="Your account balance updated",
            label_ids=["INBOX"],
            received_at=datetime(2026, 4, 2, 11, 0, 0),
            local_label="financial",
            local_label_confidence=0.9,
            manual_classification=False,
        ),
        GmailStoredMessage(
            account_id="primary",
            message_id="bootstrap-1",
            sender="Deals <deals@example.com>",
            recipients=["primary@example.com", "friend@example.com", "list@example.com", "team@example.com"],
            subject="Big sale today",
            snippet="Unsubscribe here for 50% off https://example.com",
            label_ids=["CATEGORY_PROMOTIONS", "INBOX"],
            received_at=datetime(2026, 4, 2, 10, 0, 0),
            raw_payload='{"payload":{"headers":[{"name":"List-Unsubscribe","value":"<mailto:stop@example.com>"}]}}',
        ),
        GmailStoredMessage(
            account_id="primary",
            message_id="sent-1",
            sender="Me <primary@example.com>",
            recipients=["other@example.com"],
            subject="Sent message",
            snippet="already sent",
            label_ids=["SENT"],
            received_at=datetime(2026, 4, 2, 9, 0, 0),
        ),
        GmailStoredMessage(
            account_id="primary",
            message_id="unknown-1",
            sender="Unknown <unknown@example.com>",
            recipients=["primary@example.com"],
            subject="Hello",
            snippet="Just checking in",
            label_ids=["INBOX"],
            received_at=datetime(2026, 4, 2, 8, 0, 0),
            local_label="unknown",
            local_label_confidence=0.2,
            manual_classification=False,
        ),
    ]

    dataset, summary = build_training_dataset(messages, my_addresses=["primary@example.com"], bootstrap_threshold=3.0)

    assert [row.message_id for row in dataset] == ["manual-1", "local-1", "bootstrap-1"]
    assert [row.label_source for row in dataset] == ["manual", "local_auto", "gmail_bootstrap"]
    assert [row.sample_weight for row in dataset] == [1.0, 0.75, 0.3]
    assert dataset[2].label == GmailTrainingLabel.MARKETING
    assert "CATEGORY_PROMOTIONS" not in dataset[2].normalized_text
    assert summary.total_rows_scanned == 5
    assert summary.excluded_mailbox_count == 1
    assert summary.excluded_no_label_count == 1
    assert summary.included_by_label_source == {"manual": 1, "local_auto": 1, "gmail_bootstrap": 1}
    assert summary.per_label_counts == {"direct_human": 1, "financial": 1, "marketing": 1}
    assert summary.weighted_counts == {"direct_human": 1.0, "financial": 0.75, "marketing": 0.3}


def test_gmail_training_dataset_can_disable_bootstrap_rows():
    messages = [
        GmailStoredMessage(
            account_id="primary",
            message_id="bootstrap-only",
            sender="Deals <deals@example.com>",
            recipients=["primary@example.com", "friend@example.com", "list@example.com", "team@example.com"],
            subject="Big sale today",
            snippet="Unsubscribe here for 50% off https://example.com",
            label_ids=["CATEGORY_PROMOTIONS", "INBOX"],
            received_at=datetime(2026, 4, 2, 10, 0, 0),
            raw_payload='{"payload":{"headers":[{"name":"List-Unsubscribe","value":"<mailto:stop@example.com>"}]}}',
        )
    ]

    dataset, summary = build_training_dataset(
        messages,
        my_addresses=["primary@example.com"],
        bootstrap_threshold=3.0,
        allow_bootstrap=False,
    )

    assert dataset == []
    assert summary.excluded_no_label_count == 1
