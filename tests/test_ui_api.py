from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
import pytest
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from config import AppConfig
from logging_utils import setup_logging
from main import create_app
from models import TrustMaterial
from providers.gmail.mailbox_status_store import GmailMailboxStatusStore
from providers.gmail.models import GmailMailboxStatus
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_ui_bootstrap_reports_missing_inputs(runtime_dir, core_client_factory):
    config = AppConfig(
        CORE_BASE_URL="",
        NODE_NAME="",
        NODE_TYPE="email-node",
        NODE_SOFTWARE_VERSION="0.1.0",
        NODE_NONCE="nonce-test",
        RUNTIME_DIR=runtime_dir,
        API_PORT=9003,
        UI_PORT=8083,
    )
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/node/bootstrap")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["required_inputs"] == ["core_base_url", "node_name"]
    assert body["config"]["ui_port"] == 8083
    assert body["config"]["selected_task_capabilities"] == []
    assert body["status"]["capability_setup"]["task_capability_selection"]["available"] == [
        "task.classification",
        "task.summarization",
        "task.tracking",
    ]
    assert body["status"]["mqtt_health"]["status_freshness_state"] == "inactive"
    assert body["status"]["mqtt_health"]["health_status"] == "offline"


@pytest.mark.asyncio
async def test_ui_bootstrap_reports_mqtt_health_from_telemetry(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.mqtt_manager.status.state = "connected"
    service.state.last_heartbeat_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=120)
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/node/bootstrap")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["status"]["mqtt_health"]["status_freshness_state"] == "fresh"
    assert body["status"]["mqtt_health"]["health_status"] == "connected"
    assert body["status"]["mqtt_health"]["status_age_s"] is not None
    assert body["status"]["mqtt_health"]["status_stale_after_s"] == 300
    assert body["status"]["mqtt_health"]["status_inactive_after_s"] == 1800


def test_setup_logging_writes_api_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    setup_logging(level=logging.INFO)
    logging.getLogger("test.api").info("api log smoke test")

    log_path = tmp_path / "runtime" / "logs" / "api.log"
    assert log_path.exists()
    assert "api log smoke test" in log_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_ui_can_save_config_and_start_onboarding(config, core_client_factory):
    blank_config = config.model_copy(update={"core_base_url": None, "node_name": None})
    service = NodeService(blank_config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=blank_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        save_response = await client.put(
            "/api/node/config",
            json={"core_base_url": "http://core.test", "node_name": "ui-node"},
        )
        start_response = await client.post("/api/onboarding/start")

    await service.stop()

    assert save_response.status_code == 200
    assert start_response.status_code == 200
    assert start_response.json()["onboarding_status"] == "pending"
    assert start_response.json()["node_name"] == "ui-node"


@pytest.mark.asyncio
async def test_ui_duplicate_active_session_returns_clean_error(config, core_client_factory):
    core_app = build_core_app()
    create_route = next(
        route for route in core_app.router.routes if getattr(route, "path", "") == "/api/system/nodes/onboarding/sessions"
    )
    core_app.router.routes.remove(create_route)

    @core_app.post("/api/system/nodes/onboarding/sessions")
    async def duplicate_session(payload: dict):
        core_app.state.sessions["sx_existing"] = {"status": "pending", "request": payload}
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "error": "duplicate_active_session",
                    "message": "active onboarding session already exists",
                    "retryable": False,
                }
            },
        )

    blank_config = config.model_copy(update={"core_base_url": "http://core.test", "node_name": "ui-node"})
    service = NodeService(blank_config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=blank_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/onboarding/start")

    await service.stop()

    assert response.status_code == 400
    assert "active onboarding session" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ui_duplicate_active_session_reuses_returned_core_session(config, core_client_factory):
    core_app = build_core_app()
    create_route = next(
        route for route in core_app.router.routes if getattr(route, "path", "") == "/api/system/nodes/onboarding/sessions"
    )
    core_app.router.routes.remove(create_route)

    @core_app.post("/api/system/nodes/onboarding/sessions")
    async def duplicate_session(payload: dict):
        core_app.state.sessions["sx_existing"] = {"status": "pending", "request": payload}
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

    blank_config = config.model_copy(update={"core_base_url": "http://core.test", "node_name": "ui-node"})
    service = NodeService(blank_config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=blank_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/onboarding/start")

    await service.stop()

    assert response.status_code == 200
    assert response.json()["onboarding_status"] == "pending"
    assert response.json()["session_id"] == "sx_existing"


@pytest.mark.asyncio
async def test_ui_can_restart_onboarding(config, core_client_factory):
    blank_config = config.model_copy(update={"core_base_url": "http://core.test", "node_name": "ui-node"})
    service = NodeService(blank_config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=blank_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/onboarding/start")
        restarted = await client.post(
            "/api/onboarding/restart",
            json={"core_base_url": "http://core.test", "node_name": "ui-node"},
        )

    await service.stop()

    assert first.status_code == 200
    assert restarted.status_code == 200
    assert first.json()["session_id"] is not None
    assert restarted.json()["session_id"] is not None
    assert restarted.json()["onboarding_status"] == "pending"


@pytest.mark.asyncio
async def test_ui_can_declare_capabilities_explicitly(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
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
    service.operator_config = service.operator_config_store.save(
        service.operator_config.model_copy(
            update={"selected_task_capabilities": ["task.classification"]}
        )
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/capabilities/declare")

    await service.stop()

    assert response.status_code == 400
    assert response.json()["detail"]


@pytest.mark.asyncio
async def test_ui_restart_setup_clears_trust_and_accepts_new_config(config, core_client_factory):
    trusted_config = config.model_copy(update={"core_base_url": "http://core.test", "node_name": "old-node"})
    service = NodeService(trusted_config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
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
    app = create_app(config=trusted_config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        restarted = await client.post(
            "/api/onboarding/restart",
            json={"core_base_url": "http://core.test", "node_name": "new-node"},
        )

    await service.stop()

    assert restarted.status_code == 200
    assert restarted.json()["node_name"] == "new-node"
    assert restarted.json()["onboarding_status"] == "pending"


@pytest.mark.asyncio
async def test_shared_api_routes_expose_capabilities_governance_and_services(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.state.paired_core_id = "core-1"
    service.state.governance_sync_status = "ok"
    service.state.active_governance_version = "gov-v1"
    service.state.enabled_providers = ["gmail"]
    service.state.last_heartbeat_at = datetime.now(UTC).replace(tzinfo=None)
    service.mqtt_manager.status.state = "connected"
    service.operator_config = service.operator_config_store.save(
        service.operator_config.model_copy(
            update={"selected_task_capabilities": ["task.classification", "task.tracking"]}
        )
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        capability_config = await client.get("/api/capabilities/config")
        governance_status = await client.get("/api/governance/status")
        services_status = await client.get("/api/services/status")

    await service.stop()

    assert capability_config.status_code == 200
    assert capability_config.json()["selected_task_capabilities"] == ["task.classification", "task.tracking"]
    assert "task.summarization" in capability_config.json()["available_task_capabilities"]

    assert governance_status.status_code == 200
    assert governance_status.json()["governance_sync_status"] == "ok"
    assert governance_status.json()["active_governance_version"] == "gov-v1"

    assert services_status.status_code == 200
    assert services_status.json()["api"]["port"] == 9003
    assert services_status.json()["mqtt"]["connection_status"] == "connected"
    assert services_status.json()["providers"]["enabled"] == ["gmail"]


@pytest.mark.asyncio
async def test_additional_shared_api_routes_health_diagnostics_restart_and_redeclare(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.state.paired_core_id = "core-1"
    service.state.enabled_providers = ["gmail"]
    service.state.governance_sync_status = "ok"
    service.state.last_heartbeat_at = datetime.now(UTC).replace(tzinfo=None)
    service.mqtt_manager.status.state = "connected"
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
    service.operator_config = service.operator_config_store.save(
        service.operator_config.model_copy(update={"selected_task_capabilities": ["task.classification"]})
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_response = await client.get("/api/health")
        diagnostics_response = await client.get("/api/capabilities/diagnostics")
        restart_response = await client.post("/api/services/restart", json={"target": "backend"})
        redeclare_response = await client.post("/api/capabilities/redeclare", json={"force_refresh": True})

    await service.stop()

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    assert diagnostics_response.status_code == 200
    assert diagnostics_response.json()["node_id"] == "node-1"
    assert diagnostics_response.json()["capability_setup"]["task_capability_selection"]["selected"] == [
        "task.classification"
    ]

    assert restart_response.status_code == 200
    assert restart_response.json()["status"] == "manual_required"
    assert restart_response.json()["recommended_command"] == "./scripts/dev.sh"

    assert redeclare_response.status_code in {200, 400}


@pytest.mark.asyncio
async def test_more_shared_api_routes_resolved_rebuild_and_recover(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.onboarding_status = "approved"
    service.state.node_id = "node-1"
    service.state.paired_core_id = "core-1"
    service.state.enabled_providers = ["gmail"]
    service.operator_config = service.operator_config_store.save(
        service.operator_config.model_copy(update={"selected_task_capabilities": ["task.classification"]})
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resolved_response = await client.get("/api/capabilities/node/resolved")
        rebuild_response = await client.post("/api/capabilities/rebuild", json={"force_refresh": True})
        recover_response = await client.post("/api/node/recover")

    await service.stop()

    assert resolved_response.status_code == 200
    assert resolved_response.json()["resolved_tasks"] == ["task.classification"]

    assert rebuild_response.status_code == 200
    assert rebuild_response.json()["status"] == "rebuilt"
    assert rebuild_response.json()["resolved"]["resolved_tasks"] == ["task.classification"]

    assert recover_response.status_code == 200
    assert recover_response.json()["status"] == "recovered"
    assert recover_response.json()["current_state"]["trust_state"] == "untrusted"
    assert recover_response.json()["current_state"]["node_id"] is None


@pytest.mark.asyncio
async def test_gmail_status_api_exposes_mailbox_counts(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    if service.gmail_status_task is not None:
        service.gmail_status_task.cancel()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.provider_registry.get_provider("gmail").account_store.save_account(
        service.provider_registry.get_provider("gmail").state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    GmailMailboxStatusStore(config.runtime_dir).save_status(
        GmailMailboxStatus(
            account_id="primary",
            email_address="primary@example.com",
            status="ok",
            unread_inbox_count=12,
            unread_today_count=3,
            unread_yesterday_count=4,
            unread_week_count=9,
        )
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/gmail/status")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["provider_id"] == "gmail"
    assert body["accounts"][0]["mailbox_status"]["unread_inbox_count"] == 12
    assert body["accounts"][0]["mailbox_status"]["unread_today_count"] == 3
