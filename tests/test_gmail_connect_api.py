from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from config import AppConfig
from main import create_app
from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.models import GmailOAuthConfig
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_gmail_connect_start_returns_connect_url_for_trusted_node(config, core_client_factory):
    isolated_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(
        isolated_config,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
    )
    GmailProviderConfigStore(isolated_config.runtime_dir).save(
        GmailOAuthConfig(
            enabled=True,
            client_id="client-id",
            client_secret_ref="env:GMAIL_CLIENT_SECRET",
            redirect_uri="http://127.0.0.1:9002/providers/gmail/oauth/callback",
        )
    )
    await service.start()
    service.state.trust_state = "trusted"
    app = create_app(config=isolated_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/providers/gmail/accounts/primary/connect/start",
            headers={"X-Correlation-Id": "corr-123"},
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["provider_id"] == "gmail"
    assert body["account_id"] == "primary"
    assert "accounts.google.com" in body["connect_url"]


@pytest.mark.asyncio
async def test_gmail_connect_start_requires_trusted_node(config, core_client_factory):
    isolated_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(
        isolated_config,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
    )
    await service.start()
    app = create_app(config=isolated_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/providers/gmail/accounts/primary/connect/start")

    await service.stop()

    assert response.status_code == 400
    assert "trusted node" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_gmail_connect_start_validates_gmail_config(config, core_client_factory):
    config_with_blank_runtime = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(
        config_with_blank_runtime,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
    )
    GmailProviderConfigStore(config_with_blank_runtime.runtime_dir).save(GmailOAuthConfig(enabled=True))
    await service.start()
    service.state.trust_state = "trusted"
    app = create_app(config=config_with_blank_runtime, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/providers/gmail/accounts/primary/connect/start")

    await service.stop()

    assert response.status_code == 400
    assert "configuration is incomplete" in response.json()["detail"].lower()
