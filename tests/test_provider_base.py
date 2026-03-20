from __future__ import annotations

import pytest

from providers.gmail.adapter import GmailProviderAdapter


@pytest.mark.asyncio
async def test_gmail_adapter_exposes_phase2_placeholder_contract(tmp_path):
    adapter = GmailProviderAdapter(tmp_path)

    validation = await adapter.validate_static_config()
    provider_state = await adapter.get_provider_state()
    accounts = await adapter.list_accounts()
    health = await adapter.get_account_health("primary")

    assert validation.ok is False
    assert "client_id" in validation.missing_fields
    assert provider_state == "disabled"
    assert accounts == []
    assert health.status == "invalid_config"
    assert adapter.get_enabled_status() is False
