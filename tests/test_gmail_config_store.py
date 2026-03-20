from __future__ import annotations

import json

import pytest

from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.models import GmailOAuthConfig


def test_gmail_config_store_loads_and_saves_static_config(tmp_path):
    store = GmailProviderConfigStore(tmp_path)
    config = GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="http://127.0.0.1:9002/providers/gmail/oauth/callback",
    )

    store.save(config)
    loaded = store.load()

    assert loaded.client_id == "client-id"
    assert loaded.client_secret_ref == "env:GMAIL_CLIENT_SECRET"


def test_gmail_config_store_reports_missing_required_fields(tmp_path):
    store = GmailProviderConfigStore(tmp_path)

    result = store.validate(GmailOAuthConfig())

    assert result.ok is False
    assert result.missing_fields == ["client_id", "client_secret_ref", "redirect_uri"]


def test_gmail_config_store_rejects_malformed_json(tmp_path):
    store = GmailProviderConfigStore(tmp_path)
    store.layout.provider_config_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(GmailProviderConfigError):
        store.load()


def test_gmail_config_store_does_not_allow_token_fields_in_static_config(tmp_path):
    store = GmailProviderConfigStore(tmp_path)
    store.layout.provider_config_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "client_id": "client-id",
                "client_secret_ref": "env:GMAIL_CLIENT_SECRET",
                "redirect_uri": "http://127.0.0.1:9002/providers/gmail/oauth/callback",
                "access_token": "should-not-be-here",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(GmailProviderConfigError):
        store.load()
