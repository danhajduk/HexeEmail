from __future__ import annotations

from providers.gmail.runtime import GmailRuntimeLayout


def test_gmail_runtime_layout_creates_expected_directories_and_config_file(tmp_path):
    layout = GmailRuntimeLayout(tmp_path)

    layout.ensure_layout()

    assert layout.provider_dir.is_dir()
    assert layout.accounts_dir.is_dir()
    assert layout.oauth_sessions_dir.is_dir()
    assert layout.provider_config_path.is_file()
    assert layout.provider_config_path.read_text(encoding="utf-8") == "{}\n"


def test_gmail_runtime_layout_derives_account_and_session_paths(tmp_path):
    layout = GmailRuntimeLayout(tmp_path)

    assert layout.account_file("primary").name == "primary.json"
    assert layout.oauth_session_file("state-token").name == "state-token.json"
