from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport

from core.capability_client import CapabilityClient, CapabilityManifestBuilder
from core.governance_client import GovernanceClient
from models import TrustMaterial
from providers.models import ProviderAccountRecord, ProviderHealth, ProviderId, ProviderValidationResult
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


def test_capability_manifest_builder_starts_with_supported_only_when_gmail_not_connected():
    manifest = CapabilityManifestBuilder().build(
        node_id="node-1",
        node_type="email-node",
        node_name="email-node-test",
        node_software_version="0.1.0",
        declared_task_families=[
            "task.classification",
            "task.summarization",
            "task.tracking",
        ],
        supported_providers=["gmail"],
        enabled_providers=[],
    )

    assert manifest.supported_providers == ["gmail"]
    assert manifest.enabled_providers == []
    assert manifest.declared_task_families == [
        "task.classification",
        "task.summarization",
        "task.tracking",
    ]


@pytest.mark.asyncio
async def test_trusted_runtime_waits_for_provider_and_capability_selection_before_declaring(core_client_factory, config):
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
    service.operator_config = service.operator_config_store.save(
        service.operator_config.model_copy(
            update={
                "selected_task_capabilities": [
                    "task.classification",
                    "task.summarization",
                    "task.tracking",
                ]
            }
        )
    )
    core_app.state.sessions["sx_123"]["status"] = "approved"
    await asyncio.sleep(0.08)

    status = await service.status()
    health = service.health_snapshot()

    await service.stop()

    assert service.state.capability_declaration_status == "pending"
    assert service.state.governance_sync_status == "pending"
    assert core_app.state.capabilities == {}
    assert status.capability_declaration_status == "pending"
    assert status.governance_sync_status == "pending"
    assert status.supported_providers == ["gmail"]
    assert status.enabled_providers == []
    assert health["ready"] is False
    assert health["operational_readiness"] is False


@pytest.mark.asyncio
async def test_capability_setup_summary_reports_selection_blocker_when_no_tasks_selected(core_client_factory, config):
    core_app = build_core_app()
    service = NodeService(
        config,
        core_client=core_client_factory(core_app),
        mqtt_manager=FakeMQTTManager(),
        capability_client=CapabilityClient(transport=ASGITransport(app=core_app)),
        governance_client=GovernanceClient(transport=ASGITransport(app=core_app)),
    )

    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    status = await service.status()
    await service.stop()

    assert status.capability_setup["task_capability_selection"]["configured"] is False
    assert "select at least one task capability" in status.capability_setup["blocking_reasons"]


@pytest.mark.asyncio
async def test_trusted_runtime_declares_capabilities_when_provider_and_selection_are_ready(core_client_factory, config):
    core_app = build_core_app()
    mqtt = FakeMQTTManager()
    service = NodeService(
        config,
        core_client=core_client_factory(core_app),
        mqtt_manager=mqtt,
        capability_client=CapabilityClient(transport=ASGITransport(app=core_app)),
        governance_client=GovernanceClient(transport=ASGITransport(app=core_app)),
    )

    adapter = service.provider_registry.get_provider("gmail")

    async def valid_config():
        return ProviderValidationResult(ok=True)

    async def connected_state():
        return "connected"

    async def connected_accounts():
        return [ProviderAccountRecord(provider_id=ProviderId.GMAIL, account_id="primary", status="connected")]

    async def healthy_account(account_id: str):
        return ProviderHealth(provider_id=ProviderId.GMAIL, account_id=account_id, status="connected")

    adapter.validate_static_config = valid_config  # type: ignore[method-assign]
    adapter.get_provider_state = connected_state  # type: ignore[method-assign]
    adapter.list_accounts = connected_accounts  # type: ignore[method-assign]
    adapter.get_account_health = healthy_account  # type: ignore[method-assign]
    adapter.get_enabled_status = lambda: True  # type: ignore[method-assign]

    await service.start()
    service.operator_config = service.operator_config_store.save(
        service.operator_config.model_copy(
            update={"selected_task_capabilities": ["task.classification", "task.summarization"]}
        )
    )
    core_app.state.sessions["sx_123"]["status"] = "approved"
    await asyncio.sleep(0.08)

    status = await service.status()
    await service.stop()

    assert service.state.capability_declaration_status == "accepted"
    assert service.state.governance_sync_status == "ok"
    assert service.state.active_governance_version == "phase2-test"
    assert core_app.state.capabilities["node-1"]["declared_task_families"] == [
        "task.classification",
        "task.summarization",
    ]
    assert core_app.state.capabilities["node-1"]["enabled_providers"] == ["gmail"]
    assert status.enabled_providers == ["gmail"]


@pytest.mark.asyncio
async def test_governance_sync_uses_refresh_route_after_initial_version_is_known(core_client_factory, config):
    core_app = build_core_app()
    service = NodeService(
        config,
        core_client=core_client_factory(core_app),
        mqtt_manager=FakeMQTTManager(),
        capability_client=CapabilityClient(transport=ASGITransport(app=core_app)),
        governance_client=GovernanceClient(transport=ASGITransport(app=core_app)),
    )
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.trust_material = service.trust_store.save(
        TrustMaterial(
            node_id="node-1",
            node_type="email-node",
            paired_core_id="core-1",
            node_trust_token="trust-secret",
            operational_mqtt_identity="mqtt-user",
            operational_mqtt_token="mqtt-secret",
            operational_mqtt_host="127.0.0.2",
            operational_mqtt_port=1883,
        )
    )

    await service._sync_governance()
    await service._sync_governance()
    await service.stop()

    assert core_app.state.governance_refresh_requests[-1] == {
        "node_id": "node-1",
        "current_governance_version": "phase2-test",
    }
