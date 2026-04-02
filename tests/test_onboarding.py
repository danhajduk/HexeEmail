from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.responses import JSONResponse

from config import AppConfig
from core_client import OnboardingSessionRequest
from models import OperatorConfigInput
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_onboarding_request_creation(core_client_factory, config):
    core_app = build_core_app()
    client = core_client_factory(core_app)
    request = OnboardingSessionRequest(
        node_name=config.node_name,
        node_type=config.node_type,
        node_software_version=config.node_software_version,
        protocol_version=config.onboarding_protocol_version,
        node_nonce=config.node_nonce,
        hostname="test-host",
    )
    response = await client.create_onboarding_session(config.core_base_url or "", request, "corr-1")
    await client.aclose()

    assert response.session_id == "sx_123"
    assert core_app.state.sessions["sx_123"]["request"]["node_name"] == "email-node-test"


@pytest.mark.asyncio
async def test_onboarding_request_creation_accepts_wrapped_session_payload(core_client_factory, config):
    core_app = build_core_app()
    create_route = next(
        route for route in core_app.router.routes if getattr(route, "path", "") == "/api/system/nodes/onboarding/sessions"
    )
    core_app.router.routes.remove(create_route)

    @core_app.post("/api/system/nodes/onboarding/sessions")
    async def create_wrapped_session(payload: dict):
        return {
            "ok": True,
            "session": {
                "session_id": "sx_wrapped",
                "approval_url": "http://core.test/approve/sx_wrapped",
                "expires_at": "2026-03-20T12:00:00+00:00",
                "node_type": "email",
                "requested_node_type": "email-node",
                "finalize": {"method": "GET", "path": "/api/system/nodes/onboarding/sessions/sx_wrapped/finalize"},
            },
        }

    client = core_client_factory(core_app)
    request = OnboardingSessionRequest(
        node_name=config.node_name,
        node_type=config.node_type,
        node_software_version=config.node_software_version,
        protocol_version=config.onboarding_protocol_version,
        node_nonce=config.node_nonce,
        hostname="test-host",
    )
    response = await client.create_onboarding_session(config.core_base_url or "", request, "corr-1")
    await client.aclose()

    assert response.session_id == "sx_wrapped"
    assert response.approval_url == "http://core.test/approve/sx_wrapped"


@pytest.mark.asyncio
async def test_onboarding_request_creation_accepts_duplicate_session_payload_in_error_detail(core_client_factory, config):
    core_app = build_core_app()
    create_route = next(
        route for route in core_app.router.routes if getattr(route, "path", "") == "/api/system/nodes/onboarding/sessions"
    )
    core_app.router.routes.remove(create_route)

    @core_app.post("/api/system/nodes/onboarding/sessions")
    async def create_duplicate_with_session(payload: dict):
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "error": "duplicate_active_session",
                    "message": "active onboarding session already exists",
                    "session": {
                        "session_id": "sx_existing",
                        "approval_url": "http://core.test/approve/sx_existing",
                        "expires_at": "2026-03-20T12:00:00+00:00",
                        "finalize": {"method": "GET", "path": "/api/system/nodes/onboarding/sessions/sx_existing/finalize"},
                    },
                }
            },
        )

    client = core_client_factory(core_app)
    request = OnboardingSessionRequest(
        node_name=config.node_name,
        node_type=config.node_type,
        node_software_version=config.node_software_version,
        protocol_version=config.onboarding_protocol_version,
        node_nonce=config.node_nonce,
        hostname="test-host",
    )
    response = await client.create_onboarding_session(config.core_base_url or "", request, "corr-1")
    await client.aclose()

    assert response.session_id == "sx_existing"
    assert response.approval_url == "http://core.test/approve/sx_existing"


@pytest.mark.asyncio
async def test_finalize_handling_and_trust_persistence(core_client_factory, config, runtime_dir: Path):
    core_app = build_core_app()
    core_client = core_client_factory(core_app)
    mqtt_manager = FakeMQTTManager()
    service = NodeService(config, core_client=core_client, mqtt_manager=mqtt_manager)

    await service.start()
    core_app.state.sessions["sx_123"]["status"] = "approved"
    await asyncio.sleep(0.05)

    assert service.state.trust_state == "trusted"
    assert service.state.node_id == "node-1"
    assert (runtime_dir / "trust_material.json").exists()
    assert mqtt_manager.connected_with is not None

    await service.stop()


@pytest.mark.asyncio
async def test_restart_resume_logic(core_client_factory, config):
    core_app = build_core_app()
    core_client = core_client_factory(core_app)
    service = NodeService(config, core_client=core_client, mqtt_manager=FakeMQTTManager())

    await service.start()
    assert service.state.onboarding_status == "pending"
    await service.stop()

    core_client_2 = core_client_factory(core_app)
    resumed = NodeService(config, core_client=core_client_2, mqtt_manager=FakeMQTTManager())
    await resumed.start()
    assert resumed.state.onboarding_session_id == "sx_123"
    assert resumed.state.onboarding_status == "pending"
    await resumed.stop()


@pytest.mark.asyncio
async def test_failure_case_marks_rejected(core_client_factory, config):
    core_app = build_core_app()
    core_client = core_client_factory(core_app)
    service = NodeService(config, core_client=core_client, mqtt_manager=FakeMQTTManager())
    await service.start()

    core_app.state.sessions["sx_123"]["status"] = "rejected"
    await asyncio.sleep(0.05)

    assert service.state.onboarding_status == "rejected"
    assert service.state.trust_state == "rejected"
    await service.stop()


@pytest.mark.asyncio
async def test_service_waits_for_operator_inputs_when_missing(runtime_dir: Path, core_client_factory):
    config = AppConfig(
        CORE_BASE_URL="",
        NODE_NAME="",
        NODE_TYPE="email-node",
        NODE_SOFTWARE_VERSION="0.1.0",
        NODE_NONCE="nonce-test",
        RUNTIME_DIR=runtime_dir,
        API_PORT=9003,
        UI_PORT=8083,
        ONBOARDING_POLL_INTERVAL_SECONDS=0.01,
        MQTT_HEARTBEAT_SECONDS=0.01,
    )
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    await service.start()
    assert service.state.onboarding_status == "not_started"
    assert service.required_inputs() == ["core_base_url", "node_name"]
    await service.stop()


@pytest.mark.asyncio
async def test_operator_config_update_then_start_onboarding(core_client_factory, config):
    blank_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(blank_config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    await service.start()
    await service.update_operator_config(
        OperatorConfigInput(core_base_url="http://core.test", node_name="ui-node"),
    )
    status = await service.start_onboarding()

    assert status.node_name == "ui-node"
    assert service.state.onboarding_status == "pending"
    await service.stop()


@pytest.mark.asyncio
async def test_start_onboarding_reports_resolved_ip_to_core(core_client_factory, config):
    core_app = build_core_app()
    core_client = core_client_factory(core_app)
    service = NodeService(config, core_client=core_client, mqtt_manager=FakeMQTTManager())

    await service.start()
    service._resolve_advertised_host = lambda: "192.168.1.50"  # type: ignore[method-assign]
    await service.start_onboarding(force=True)

    assert core_app.state.sessions["sx_123"]["request"]["hostname"] == "192.168.1.50"
    assert core_app.state.sessions["sx_123"]["request"]["ui_endpoint"] == "http://192.168.1.50:8083"
    assert core_app.state.sessions["sx_123"]["request"]["api_base_url"] == "http://192.168.1.50:9003/api"
    await service.stop()


@pytest.mark.asyncio
async def test_restart_onboarding_forces_fresh_session(core_client_factory, config):
    blank_config = config.model_copy(update={"core_base_url": "http://core.test", "node_name": "ui-node"})
    service = NodeService(blank_config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    await service.start()
    first = await service.start_onboarding()
    service.state.last_error = "stale session"
    service.state_store.save(service.state)
    second = await service.restart_onboarding()

    assert first.session_id is not None
    assert second.session_id is not None
    assert service.state.onboarding_status == "pending"
    assert service.state.last_error is None
    await service.stop()
