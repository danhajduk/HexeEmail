from __future__ import annotations

from datetime import datetime

from providers.gmail.models import GmailStoredMessage
from providers.gmail.training import NORMALIZATION_VERSION, flatten_message, render_flat_training_text


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
