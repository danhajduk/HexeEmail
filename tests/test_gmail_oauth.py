from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from providers.gmail.models import GmailOAuthSessionState
from providers.gmail.oauth import GmailOAuthSessionManager, GmailOAuthStateError


def test_gmail_oauth_session_manager_creates_and_persists_session(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)

    session = manager.create_session("primary", correlation_id="corr-123")
    loaded = manager.load_session(session.state)

    assert loaded.account_id == "primary"
    assert loaded.correlation_id == "corr-123"
    assert loaded.consumed_at is None


def test_gmail_oauth_session_manager_rejects_consumed_state(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)
    session = manager.create_session("primary")

    manager.consume_session(session.state)

    with pytest.raises(GmailOAuthStateError):
        manager.validate_callback_state(session.state)


def test_gmail_oauth_session_manager_rejects_expired_state(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)
    session = GmailOAuthSessionState(
        state="expired-state",
        account_id="primary",
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
    )
    manager.save_session(session)

    with pytest.raises(GmailOAuthStateError):
        manager.validate_callback_state("expired-state")


def test_gmail_oauth_session_manager_expires_stale_sessions(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)
    stale = GmailOAuthSessionState(
        state="stale-state",
        account_id="primary",
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
    )
    fresh = GmailOAuthSessionState(
        state="fresh-state",
        account_id="primary",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5),
    )
    manager.save_session(stale)
    manager.save_session(fresh)

    expired_count = manager.expire_stale_sessions()

    assert expired_count == 1
    assert manager.load_session("stale-state").consumed_at is not None
    assert manager.load_session("fresh-state").consumed_at is None
