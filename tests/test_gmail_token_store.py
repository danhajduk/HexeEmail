from __future__ import annotations

from providers.gmail.models import GmailTokenRecord
from providers.gmail.token_store import GmailTokenStore


def test_gmail_token_store_saves_and_loads_token_record(tmp_path):
    store = GmailTokenStore(tmp_path)
    token = GmailTokenRecord(
        account_id="primary",
        access_token="access-token",
        refresh_token="refresh-token",
        granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
    )

    store.save_token("primary", token)
    loaded = store.load_token("primary")

    assert loaded is not None
    assert loaded.account_id == "primary"
    assert loaded.refresh_token == "refresh-token"


def test_gmail_token_store_tracks_token_presence_and_deletion(tmp_path):
    store = GmailTokenStore(tmp_path)
    token = GmailTokenRecord(account_id="primary", access_token="access-token")

    assert store.token_exists("primary") is False
    store.save_token("primary", token)
    assert store.token_exists("primary") is True
    store.delete_token("primary")
    assert store.token_exists("primary") is False
