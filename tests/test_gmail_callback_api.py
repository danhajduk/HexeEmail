from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app
from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.identity import GmailIdentityProbeClient
from providers.gmail.models import GmailOAuthConfig
from providers.gmail.oauth import GmailOAuthSessionManager
from providers.gmail.token_client import GmailTokenExchangeClient
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app
from tests.test_gmail_token_client import build_google_token_app
from tests.test_gmail_adapter import build_google_identity_app


@pytest.mark.asyncio
async def test_gmail_callback_exchanges_code_and_consumes_state(config, core_client_factory, monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret-value")
    isolated_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    token_client = GmailTokenExchangeClient(transport=ASGITransport(app=build_google_token_app()))
    token_client.TOKEN_ENDPOINT = "http://google.test/token"
    service = NodeService(
        isolated_config,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
        gmail_token_client=token_client,
    )
    GmailProviderConfigStore(isolated_config.runtime_dir).save(
        GmailOAuthConfig(
            enabled=True,
            client_id="client-id",
            client_secret_ref="env:GMAIL_CLIENT_SECRET",
            redirect_uri="http://127.0.0.1:9003/providers/gmail/oauth/callback",
        )
    )
    session = GmailOAuthSessionManager(isolated_config.runtime_dir).create_session("primary", correlation_id="corr-123")
    identity_client = GmailIdentityProbeClient(
        service.provider_registry.get_provider("gmail").account_store,
        transport=ASGITransport(app=build_google_identity_app()),
    )
    identity_client.USERINFO_ENDPOINT = "http://google.test/userinfo"
    service.provider_registry.get_provider("gmail").identity_client = identity_client
    await service.start()
    app = create_app(config=isolated_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/providers/gmail/oauth/callback",
            params={"state": session.state, "code": "auth-code"},
            headers={"X-Correlation-Id": "corr-123"},
        )

    consumed = GmailOAuthSessionManager(isolated_config.runtime_dir).load_session(session.state)
    await service.stop()

    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    assert consumed.consumed_at is not None


@pytest.mark.asyncio
async def test_gmail_callback_requires_state_and_code(config, core_client_factory):
    isolated_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(
        isolated_config,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
    )
    await service.start()
    app = create_app(config=isolated_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/providers/gmail/oauth/callback", params={"state": "only-state"})

    await service.stop()

    assert response.status_code == 400
    assert "missing required query parameters" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_gmail_callback_handles_provider_error(config, core_client_factory):
    isolated_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(
        isolated_config,
        core_client=core_client_factory(build_core_app()),
        mqtt_manager=FakeMQTTManager(),
    )
    await service.start()
    app = create_app(config=isolated_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/providers/gmail/oauth/callback",
            params={"error": "access_denied", "error_description": "operator rejected consent"},
        )

    await service.stop()

    assert response.status_code == 400
    assert "operator rejected consent" in response.json()["detail"].lower()
