from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from urllib.parse import parse_qs, urlparse

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
            redirect_uri="https://hexe-ai.com/google/gmail/callback",
        )
    )
    await service.start()
    service.operator_config.core_base_url = "http://core.test"
    service.operator_config.node_name = "email-node-test"
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.state.paired_core_id = "hexe-core"
    app = create_app(config=isolated_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/providers/gmail/accounts/primary/connect/start",
            headers={"X-Correlation-Id": "corr-123"},
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["provider_id"] == "gmail"
    assert body["account_id"] == "primary"
    assert "accounts.google.com" in body["connect_url"]
    parsed = urlparse(body["connect_url"])
    query = parse_qs(parsed.query)
    assert query["redirect_uri"] == ["https://hexe-ai.com/google/gmail/callback"]
    assert "login_hint" not in query
    payload = service.gmail_oauth_manager.verify_public_state(query["state"][0])
    assert payload["client_id"] == "client-id"
    assert payload["core_id"] == "a75d480287c33cab"


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
        response = await client.post("/api/providers/gmail/accounts/primary/connect/start")

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
        response = await client.post("/api/providers/gmail/accounts/primary/connect/start")

    await service.stop()

    assert response.status_code == 400
    assert "configuration is incomplete" in response.json()["detail"].lower()
