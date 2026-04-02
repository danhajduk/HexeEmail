from __future__ import annotations

import json

from providers.gmail.mailbox_status_store import GmailMailboxStatusStore


def test_gmail_mailbox_status_store_loads_legacy_unread_week_payload(runtime_dir):
    store = GmailMailboxStatusStore(runtime_dir)
    path = store.layout.mailbox_status_file("primary")
    path.write_text(
        json.dumps(
            {
                "account_id": "primary",
                "status": "ok",
                "email_address": "primary@example.com",
                "unread_inbox_count": 12,
                "unread_today_count": 3,
                "unread_yesterday_count": 4,
                "unread_week_count": 9,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    status = store.load_status("primary")

    assert status is not None
    assert status.unread_last_hour_count == 9
