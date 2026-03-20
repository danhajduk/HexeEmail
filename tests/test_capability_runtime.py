from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport

from core.capability_client import CapabilityClient, CapabilityManifestBuilder
from core.governance_client import GovernanceClient
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


def test_capability_manifest_builder_starts_with_supported_only_when_gmail_not_connected():
    manifest = CapabilityManifestBuilder().build(
        node_id="node-1",
        node_type="email-node",
        node_name="email-node-test",
        node_software_version="0.1.0",
        supported_providers=["gmail"],
        enabled_providers=[],
    )

    assert manifest.supported_providers == ["gmail"]
    assert manifest.enabled_providers == []
    assert "task.ingest.email" in manifest.declared_task_families


@pytest.mark.asyncio
async def test_trusted_runtime_declares_capabilities_and_fetches_governance(core_client_factory, config):
    core_app = build_core_app()
    mqtt = FakeMQTTManager()
    service = NodeService(
        config,
        core_client=core_client_factory(core_app),
        mqtt_manager=mqtt,
        capability_client=CapabilityClient(transport=ASGITransport(app=core_app)),
        governance_client=GovernanceClient(transport=ASGITransport(app=core_app)),
    )

    await service.start()
    core_app.state.sessions["sx_123"]["status"] = "approved"
    await asyncio.sleep(0.08)

    status = await service.status()
    health = service.health_snapshot()

    await service.stop()

    assert service.state.capability_declaration_status == "accepted"
    assert service.state.governance_sync_status == "ok"
    assert core_app.state.capabilities["node-1"]["supported_providers"] == ["gmail"]
    assert core_app.state.capabilities["node-1"]["enabled_providers"] == []
    assert status.capability_declaration_status == "accepted"
    assert status.governance_sync_status == "ok"
    assert status.supported_providers == ["gmail"]
    assert status.enabled_providers == []
    assert health["ready"] is False
    assert health["operational_readiness"] is False
