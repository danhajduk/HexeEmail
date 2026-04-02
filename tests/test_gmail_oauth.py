from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from providers.gmail.models import GmailOAuthConfig
from providers.gmail.models import GmailOAuthSessionState
from providers.gmail.oauth import GmailOAuthSessionManager, GmailOAuthStateError


def test_gmail_oauth_session_manager_creates_and_persists_session(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)

    session = manager.create_session(
        "primary",
        "https://email-node.example.com/api/providers/gmail/oauth/callback",
        correlation_id="corr-123",
        core_id="core-1",
        node_id="node-1",
    )
    loaded = manager.load_session(session.state)

    assert loaded.account_id == "primary"
    assert loaded.redirect_uri == "https://email-node.example.com/api/providers/gmail/oauth/callback"
    assert loaded.correlation_id == "corr-123"
    assert loaded.core_id == "core-1"
    assert loaded.node_id == "node-1"
    assert loaded.flow_id == session.state
    assert loaded.consumed_at is None
    assert loaded.code_verifier


def test_gmail_oauth_session_manager_rejects_consumed_state(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)
    session = manager.create_session("primary", "https://email-node.example.com/api/providers/gmail/oauth/callback")
    session.core_id = "core-1"
    session.node_id = "node-1"
    session.flow_id = session.state
    manager.save_session(session)

    manager.consume_session(session.state)

    with pytest.raises(GmailOAuthStateError):
        manager.validate_callback_state(session.state)


def test_gmail_oauth_session_manager_rejects_expired_state(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)
    session = GmailOAuthSessionState(
        state="expired-state",
        account_id="primary",
        redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
        code_verifier="verifier",
        core_id="core-1",
        node_id="node-1",
        flow_id="expired-state",
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
        redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
        code_verifier="verifier",
        core_id="core-1",
        node_id="node-1",
        flow_id="stale-state",
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
    )
    fresh = GmailOAuthSessionState(
        state="fresh-state",
        account_id="primary",
        redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
        code_verifier="verifier",
        core_id="core-1",
        node_id="node-1",
        flow_id="fresh-state",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5),
    )
    manager.save_session(stale)
    manager.save_session(fresh)

    expired_count = manager.expire_stale_sessions()

    assert expired_count == 1
    assert manager.load_session("stale-state").consumed_at is not None
    assert manager.load_session("fresh-state").consumed_at is None


def test_gmail_oauth_session_manager_builds_google_connect_url(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)
    oauth_config = GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
    )

    session = manager.create_connect_session(
        "primary",
        oauth_config,
        correlation_id="corr-123",
        core_id="core-1",
        node_id="node-1",
    )
    parsed = urlparse(session.authorization_url or "")
    query = parse_qs(parsed.query)
    payload = manager.verify_public_state(query["state"][0])

    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["https://hexe-ai.com/google/gmail/callback"]
    assert query["access_type"] == ["offline"]
    assert query["state"] == [session.public_state]
    assert "login_hint" not in query
    assert query["code_challenge_method"] == ["S256"]
    assert "https://www.googleapis.com/auth/gmail.send" in query["scope"][0]
    assert "https://www.googleapis.com/auth/gmail.readonly" in query["scope"][0]
    assert payload["provider"] == "gmail"
    assert payload["client_id"] == "client-id"
    assert payload["core_id"] == "core-1"
    assert payload["node_id"] == "node-1"
    assert payload["flow_id"] == session.state
    assert payload["account_id"] == "primary"


def test_gmail_oauth_session_manager_rejects_tampered_signed_state(tmp_path):
    manager = GmailOAuthSessionManager(tmp_path)
    session = manager.create_session(
        "primary",
        "https://email-node.example.com/api/providers/gmail/oauth/callback",
        core_id="core-1",
        node_id="node-1",
    )
    signed_state = manager.sign_public_state(session)

    tampered = f"{signed_state[:-1]}A"

    with pytest.raises(GmailOAuthStateError):
        manager.verify_public_state(tampered)
