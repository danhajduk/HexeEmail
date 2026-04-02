from __future__ import annotations

import pytest

from providers.gmail.models import (
    GmailAccountConfig,
    GmailOAuthConfig,
    GmailOAuthSessionState,
    GmailRequestedScopes,
    GmailTokenRecord,
)


def test_gmail_requested_scopes_default_to_send_read_and_modify_scopes():
    scopes = GmailRequestedScopes()

    assert scopes.scopes == [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]


def test_gmail_requested_scopes_require_at_least_one_non_blank_scope():
    with pytest.raises(ValueError):
        GmailRequestedScopes(scopes=[" ", ""])


def test_gmail_oauth_config_keeps_static_fields_separate_from_runtime_tokens():
    config = GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
    )

    assert config.enabled is True
    assert config.oauth_client_type == "web"
    assert config.client_secret_ref == "env:GMAIL_CLIENT_SECRET"
    assert "access_token" not in config.model_dump()


def test_gmail_oauth_config_migrates_legacy_desktop_marker_to_web():
    config = GmailOAuthConfig(
        oauth_client_type="desktop",
        client_id="client-id",
    )

    assert config.oauth_client_type == "web"


def test_gmail_oauth_config_appends_modify_scope_for_legacy_saved_configs():
    config = GmailOAuthConfig(
        enabled=True,
        requested_scopes=GmailRequestedScopes(
            scopes=[
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly",
            ]
        ),
    )

    assert config.requested_scopes.scopes == [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]


def test_gmail_account_config_supports_future_multi_account_layout():
    account = GmailAccountConfig(account_id="primary", display_name="Primary Inbox")

    assert account.account_id == "primary"
    assert account.enabled is True


def test_gmail_token_record_tracks_runtime_token_metadata():
    token = GmailTokenRecord(
        account_id="primary",
        access_token="access-token",
        refresh_token="refresh-token",
        granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
    )

    assert token.token_type == "Bearer"
    assert token.refresh_token == "refresh-token"


def test_gmail_oauth_session_state_defaults_to_short_lived_pending_session():
    session = GmailOAuthSessionState(
        state="oauth-state",
        account_id="primary",
        redirect_uri="https://email-node.example.com/api/providers/gmail/oauth/callback",
        code_verifier="verifier",
    )

    assert session.account_id == "primary"
    assert session.consumed_at is None
    assert session.expires_at > session.created_at
