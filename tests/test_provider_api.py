from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app
from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.models import GmailOAuthConfig
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_provider_endpoints_expose_gmail_summary(config, core_client_factory):
    isolated_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    GmailProviderConfigStore(isolated_config.runtime_dir).save(
        GmailOAuthConfig(
            enabled=True,
            client_id="client-id",
            client_secret_ref="env:GMAIL_CLIENT_SECRET",
        )
    )
    service = NodeService(
        isolated_config,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
    )
    await service.start()
    app = create_app(config=isolated_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        providers_response = await client.get("/providers")
        gmail_response = await client.get("/providers/gmail")
        validate_response = await client.post("/providers/gmail/validate-config")

    await service.stop()

    assert providers_response.status_code == 200
    assert "gmail" in providers_response.json()["supported_providers"]
    assert gmail_response.status_code == 200
    assert gmail_response.json()["provider_id"] == "gmail"
    assert validate_response.status_code == 200
    assert "client_secret_ref" not in str(validate_response.json())


@pytest.mark.asyncio
async def test_gmail_config_endpoints_round_trip_runtime_config(config, core_client_factory):
    isolated_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(
        isolated_config,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
    )
    await service.start()
    app = create_app(config=isolated_config, service=service)

    payload = {
        "oauth_client_type": "desktop",
        "enabled": True,
        "client_id": "client-id",
        "client_secret_ref": "env:GMAIL_CLIENT_SECRET",
        "requested_scopes": {"scopes": ["https://www.googleapis.com/auth/gmail.send"]},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        update_response = await client.put("/providers/gmail/config", json=payload)
        get_response = await client.get("/providers/gmail/config")

    await service.stop()

    assert update_response.status_code == 200
    assert update_response.json()["config"]["oauth_client_type"] == "desktop"
    assert update_response.json()["validation"]["ok"] is True
    assert get_response.status_code == 200
    assert get_response.json()["config"]["client_id"] == "client-id"
