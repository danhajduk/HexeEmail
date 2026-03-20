from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport

from core.capability_client import CapabilityClient
from core.governance_client import GovernanceClient
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_phase1_acceptance_flow(core_client_factory, config):
    core_app = build_core_app()
    core_client = core_client_factory(core_app)
    capability_client = CapabilityClient(transport=ASGITransport(app=core_app))
    governance_client = GovernanceClient(transport=ASGITransport(app=core_app))
    mqtt = FakeMQTTManager()
    service = NodeService(
        config,
        core_client=core_client,
        mqtt_manager=mqtt,
        capability_client=capability_client,
        governance_client=governance_client,
    )

    await service.start()
    assert service.state.onboarding_session_id == "sx_123"
    assert service.state.approval_url == "http://core.test/approve/sx_123"

    core_app.state.sessions["sx_123"]["status"] = "approved"
    await asyncio.sleep(0.05)

    assert service.state.trust_state == "trusted"
    assert service.state.node_id == "node-1"
    assert mqtt.status.state == "connected"

    await service.stop()

    resumed = NodeService(
        config,
        core_client=core_client_factory(core_app),
        mqtt_manager=FakeMQTTManager(),
        capability_client=CapabilityClient(transport=ASGITransport(app=core_app)),
        governance_client=GovernanceClient(transport=ASGITransport(app=core_app)),
    )
    await resumed.start()
    assert resumed.state.trust_state == "trusted"
    assert resumed.state.onboarding_status == "approved"
    await resumed.stop()
