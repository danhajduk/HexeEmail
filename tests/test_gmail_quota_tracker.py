from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from providers.gmail.quota_tracker import GmailQuotaLimitError, GmailQuotaTracker


def test_gmail_quota_tracker_records_usage(runtime_dir):
    tracker = GmailQuotaTracker(runtime_dir)

    tracker.reserve("primary", 5, "messages.list", now=datetime(2026, 4, 2, 12, 0, 0).astimezone())
    tracker.reserve("primary", 10, "messages.get", now=datetime(2026, 4, 2, 12, 0, 10).astimezone())
    snapshot = tracker.snapshot("primary", now=datetime(2026, 4, 2, 12, 0, 20).astimezone())

    assert snapshot.used_last_minute == 15
    assert snapshot.remaining_last_minute == 14985
    assert snapshot.recent_operations == {"messages.get": 10, "messages.list": 5}


def test_gmail_quota_tracker_enforces_per_user_limit(runtime_dir):
    tracker = GmailQuotaTracker(runtime_dir)
    now = datetime(2026, 4, 2, 12, 0, 0).astimezone()

    tracker.reserve("primary", 14995, "messages.list", now=now)

    with pytest.raises(GmailQuotaLimitError):
        tracker.reserve("primary", 10, "messages.get", now=now + timedelta(seconds=10))
