from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest
from fastapi import Header
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from config import AppConfig
from logging_utils import _next_six_hour_boundary_epoch, setup_logging
from main import create_app
from models import TrustMaterial
from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.fetch_schedule_store import GmailFetchScheduleStore
from providers.gmail.mailbox_client import GmailMailboxClient
from providers.gmail.mailbox_status_store import GmailMailboxStatusStore
from providers.gmail.models import (
    GmailFetchScheduleState,
    GmailFetchWindowState,
    GmailManualClassificationBatchInput,
    GmailMailboxStatus,
    GmailOAuthConfig,
    GmailSenderReputationInputs,
    GmailSenderReputationRecord,
    GmailShipmentRecord,
    GmailSpamhausCheck,
    GmailStoredMessage,
    GmailTokenRecord,
    GmailTrainingLabel,
)
from providers.gmail.training import normalize_email_for_classifier
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
async def test_service_start_can_skip_gmail_background_loops(runtime_dir, core_client_factory):
    config = AppConfig(
        CORE_BASE_URL="http://core.test",
        NODE_NAME="node-test",
        NODE_TYPE="email-node",
        NODE_SOFTWARE_VERSION="0.1.0",
        NODE_NONCE="nonce-test",
        RUNTIME_DIR=runtime_dir,
        API_PORT=9003,
        UI_PORT=8083,
        GMAIL_STATUS_POLL_ON_STARTUP=False,
        GMAIL_FETCH_POLL_ON_STARTUP=False,
    )
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    await service.start()

    assert service.gmail_status_task is None
    assert service.gmail_fetch_task is None

    await service.stop()


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
    logging.getLogger("providers.gmail.test").info("provider log smoke test")
    logging.getLogger("core_client").info("core log smoke test")
    logging.getLogger("hexe.ai.runtime").info("ai log smoke test")
    logging.getLogger("mqtt").info("mqtt log smoke test")

    log_dir = tmp_path / "runtime" / "logs"
    api_log_path = log_dir / "api.log"
    provider_log_path = log_dir / "providers.log"
    core_log_path = log_dir / "core.log"
    ai_log_path = log_dir / "ai.log"
    mqtt_log_path = log_dir / "mqtt.log"
    app_log_path = log_dir / "app.log"

    assert api_log_path.exists()
    assert "api log smoke test" in api_log_path.read_text(encoding="utf-8")
    assert provider_log_path.exists()
    assert "provider log smoke test" in provider_log_path.read_text(encoding="utf-8")
    assert core_log_path.exists()
    assert "core log smoke test" in core_log_path.read_text(encoding="utf-8")
    assert ai_log_path.exists()
    assert "ai log smoke test" in ai_log_path.read_text(encoding="utf-8")
    assert mqtt_log_path.exists()
    assert "mqtt log smoke test" in mqtt_log_path.read_text(encoding="utf-8")
    assert app_log_path.exists()
    app_log_text = app_log_path.read_text(encoding="utf-8")
    assert "api log smoke test" in app_log_text
    assert "provider log smoke test" in app_log_text


def test_logging_rotation_aligns_to_six_hour_boundaries():
    assert datetime.fromtimestamp(
        _next_six_hour_boundary_epoch(datetime(2024, 5, 1, 1, 15, 0).astimezone().timestamp())
    ).strftime("%Y-%m-%d %H:%M:%S") == "2024-05-01 06:00:00"
    assert datetime.fromtimestamp(
        _next_six_hour_boundary_epoch(datetime(2024, 5, 1, 7, 15, 0).astimezone().timestamp())
    ).strftime("%Y-%m-%d %H:%M:%S") == "2024-05-01 12:00:00"
    assert datetime.fromtimestamp(
        _next_six_hour_boundary_epoch(datetime(2024, 5, 1, 13, 15, 0).astimezone().timestamp())
    ).strftime("%Y-%m-%d %H:%M:%S") == "2024-05-01 18:00:00"
    assert datetime.fromtimestamp(
        _next_six_hour_boundary_epoch(datetime(2024, 5, 1, 19, 15, 0).astimezone().timestamp())
    ).strftime("%Y-%m-%d %H:%M:%S") == "2024-05-02 00:00:00"


def test_runtime_prompt_loader_reads_from_runtime_prompt_directory(runtime_dir, core_client_factory, monkeypatch):
    prompt_dir = runtime_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / "prompt.email.classifier.json"
    prompt_payload = {
        "prompt_id": "prompt.email.classifier",
        "version": "test-runtime-v1",
        "service_id": "node-email",
        "task_family": "task.classification",
        "prompt_name": "Email Classifier",
        "definition": {
            "template": "Classify this email: {{ normalized_text }}",
            "template_variables": ["normalized_text"],
        },
        "provider_preferences": {
            "default_provider": "openai",
            "default_model": "gpt-5.4-nano",
            "preferred_models": ["gpt-5.4-nano"],
        },
        "constraints": {
            "max_timeout_s": 60,
            "structured_output_required": True,
        },
        "node_runtime": {
            "timeout_s": 30,
            "json_schema": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                },
                "required": ["label"],
                "additionalProperties": False,
            },
        },
    }
    prompt_path.write_text(json.dumps(prompt_payload), encoding="utf-8")
    config = AppConfig(
        CORE_BASE_URL="http://core.test",
        NODE_NAME="email-node-test",
        NODE_TYPE="email-node",
        NODE_SOFTWARE_VERSION="0.1.0",
        NODE_NONCE="nonce-test",
        RUNTIME_DIR=runtime_dir,
        PROMPT_DEFINITION_DIR=prompt_dir,
        API_PORT=9003,
        UI_PORT=8083,
        ONBOARDING_POLL_INTERVAL_SECONDS=0.01,
        MQTT_HEARTBEAT_SECONDS=0.01,
    )
    monkeypatch.setattr("node_backend.runtime.RuntimeManager._legacy_prompt_definition_dir", staticmethod(lambda: Path("/tmp/does-not-exist")))
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    assert service._prompt_definition_dir() == prompt_dir
    assert service._load_runtime_prompt_definition("prompt.email.classifier")["version"] == "test-runtime-v1"


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
async def test_task_routing_preview_supports_requested_node_type(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.state.capability_declaration_status = "accepted"
    service.operator_config = service.operator_config_store.save(
        service.operator_config.model_copy(update={"selected_task_capabilities": ["task.classification"]})
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/tasks/routing/preview",
            json={
                "task_family": "task.classification",
                "requested_node_type": "ai-node",
                "inputs": {"message_id": "msg-1"},
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["task_family"] == "task.classification"
    assert body["requested_node_type"] == "ai"
    assert body["local_node_type"] == "email-node"
    assert body["local_node_can_execute"] is False
    assert body["should_delegate_to_core"] is True


@pytest.mark.asyncio
async def test_core_service_resolve_and_authorize_routes_forward_trusted_node_context(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-abc123"
    service.trust_material = service.trust_store.save(
        TrustMaterial(
            node_id="node-abc123",
            node_type="email-node",
            paired_core_id="core-1",
            node_trust_token="trust-secret",
            operational_mqtt_identity="mqtt-user",
            operational_mqtt_token="mqtt-secret",
            operational_mqtt_host="127.0.0.2",
            operational_mqtt_port=1883,
        )
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resolve_response = await client.post(
            "/api/core/services/resolve",
            json={
                "task_family": "task.summarization",
                "type": "ai",
                "task_context": {"content_type": "email"},
                "preferred_provider": "openai",
            },
        )
        authorize_response = await client.post(
            "/api/core/services/authorize",
            json={
                "task_family": "task.summarization",
                "type": "ai",
                "task_context": {"content_type": "email"},
                "service_id": "summary-service",
                "provider": "openai",
            },
        )

    await service.stop()

    assert resolve_response.status_code == 200
    assert resolve_response.json()["selected_service_id"] == "summary-service"
    assert authorize_response.status_code == 200
    assert authorize_response.json()["authorized"] is True

    assert core_app.state.service_resolve_requests == [
        {
            "node_id": "node-abc123",
            "task_family": "task.summarization",
            "type": "ai",
            "task_context": {"content_type": "email"},
            "preferred_provider": "openai",
        }
    ]
    assert core_app.state.service_authorize_requests == [
        {
            "node_id": "node-abc123",
            "task_family": "task.summarization",
            "type": "ai",
            "task_context": {"content_type": "email"},
            "service_id": "summary-service",
            "provider": "openai",
        }
    ]


@pytest.mark.asyncio
async def test_runtime_sync_prompts_registers_missing_email_classifier_prompt(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)
    classifier_definition = service._load_runtime_prompt_definition("prompt.email.classifier")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/prompts/sync",
            json={
                "target_api_base_url": "http://10.0.0.100:9002",
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    registered_ids = {item["prompt_id"] for item in body["registrations"]}
    assert "prompt.email.classifier" in registered_ids
    assert "prompt.email.action_decision" in registered_ids
    assert "prompt.email.summarization" in registered_ids
    assert body["usage_summary"] is None

    assert core_app.state.prompt_service_lifecycle_requests == []
    assert core_app.state.prompt_service_update_requests == []
    assert len(core_app.state.prompt_service_registration_requests) == 3
    registration_request = next(
        item for item in core_app.state.prompt_service_registration_requests if item["prompt_id"] == "prompt.email.classifier"
    )
    assert registration_request["prompt_id"] == "prompt.email.classifier"
    assert registration_request["version"] == classifier_definition["version"]
    assert registration_request["service_id"] == "node-email"
    assert registration_request["task_family"] == "task.classification"
    assert registration_request["provider_preferences"] == {
        "default_provider": "openai",
        "default_model": "gpt-5.4-nano",
        "preferred_models": ["gpt-5.4-nano", "gpt-5-mini"],
    }
    assert registration_request["constraints"] == {
        "max_timeout_s": 60,
        "structured_output_required": True,
    }
    assert registration_request["definition"]["template_variables"] == ["normalized_text"]
    assert service.state.runtime_prompt_sync_target_api_base_url == "http://10.0.0.100:9002"
    assert core_app.state.execution_direct_requests == []
    assert core_app.state.usage_summary_requests == []


@pytest.mark.asyncio
async def test_runtime_sync_prompts_registers_when_prompt_read_returns_not_registered_400(config, core_client_factory):
    core_app = build_core_app()
    core_app.state.prompt_read_missing_returns_400 = True
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)
    summarization_definition = service._load_runtime_prompt_definition("prompt.email.summarization")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/prompts/sync",
            json={
                "target_api_base_url": "http://10.0.0.100:9002",
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    registered_ids = {item["prompt_id"] for item in body["registrations"]}
    assert "prompt.email.summarization" in registered_ids
    assert {
        "prompt_id": "prompt.email.summarization",
        "action": "registered",
        "version": summarization_definition["version"],
        "remote_version": None,
        "remote_status": None,
    } in body["sync_actions"]


@pytest.mark.asyncio
async def test_runtime_sync_prompts_skips_current_prompt_version(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    local_classifier_version = service._load_runtime_prompt_definition("prompt.email.classifier")["version"]
    local_action_version = service._load_runtime_prompt_definition("prompt.email.action_decision")["version"]
    local_summary_version = service._load_runtime_prompt_definition("prompt.email.summarization")["version"]
    core_app.state.prompt_services["prompt.email.classifier"] = {
        "prompt_id": "prompt.email.classifier",
        "service_id": "node-email",
        "prompt_name": "Email Classifier",
        "status": "active",
        "current_version": local_classifier_version,
        "versions": [local_classifier_version],
    }
    core_app.state.prompt_services["prompt.email.action_decision"] = {
        "prompt_id": "prompt.email.action_decision",
        "service_id": "node-email",
        "prompt_name": "Email action decision",
        "status": "active",
        "current_version": local_action_version,
        "versions": [local_action_version],
    }
    core_app.state.prompt_services["prompt.email.summarization"] = {
        "prompt_id": "prompt.email.summarization",
        "service_id": "node-email",
        "prompt_name": "Email summarization",
        "status": "active",
        "current_version": local_summary_version,
        "versions": [local_summary_version],
    }
    await service.start()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/prompts/sync",
            json={"target_api_base_url": "http://10.0.0.100:9002"},
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    sync_actions = {(item["prompt_id"], item["action"], item["remote_version"]) for item in body["sync_actions"]}
    assert ("prompt.email.classifier", "unchanged", local_classifier_version) in sync_actions
    assert ("prompt.email.action_decision", "unchanged", local_action_version) in sync_actions
    assert ("prompt.email.summarization", "unchanged", local_summary_version) in sync_actions
    assert core_app.state.prompt_service_registration_requests == []
    assert core_app.state.prompt_service_update_requests == []
    assert core_app.state.prompt_service_lifecycle_requests == []


@pytest.mark.asyncio
async def test_runtime_sync_prompts_updates_outdated_prompt(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    local_classifier_version = service._load_runtime_prompt_definition("prompt.email.classifier")["version"]
    local_action_version = service._load_runtime_prompt_definition("prompt.email.action_decision")["version"]
    local_summary_version = service._load_runtime_prompt_definition("prompt.email.summarization")["version"]
    core_app.state.prompt_services["prompt.email.classifier"] = {
        "prompt_id": "prompt.email.classifier",
        "service_id": "node-email",
        "prompt_name": "Email Classifier",
        "status": "active",
        "current_version": "v0",
        "versions": ["v0"],
    }
    core_app.state.prompt_services["prompt.email.action_decision"] = {
        "prompt_id": "prompt.email.action_decision",
        "service_id": "node-email",
        "prompt_name": "Email action decision",
        "status": "active",
        "current_version": local_action_version,
        "versions": [local_action_version],
    }
    core_app.state.prompt_services["prompt.email.summarization"] = {
        "prompt_id": "prompt.email.summarization",
        "service_id": "node-email",
        "prompt_name": "Email summarization",
        "status": "active",
        "current_version": local_summary_version,
        "versions": [local_summary_version],
    }
    await service.start()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/prompts/sync",
            json={"target_api_base_url": "http://10.0.0.100:9002"},
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert {
        "prompt_id": "prompt.email.classifier",
        "action": "updated",
        "version": local_classifier_version,
        "remote_version": "v0",
        "remote_status": "active",
    } in body["sync_actions"]
    assert {
        "prompt_id": "prompt.email.action_decision",
        "action": "unchanged",
        "version": local_action_version,
        "remote_version": local_action_version,
        "remote_status": "active",
    } in body["sync_actions"]
    assert core_app.state.prompt_service_lifecycle_requests == []
    assert core_app.state.prompt_service_registration_requests == []
    assert len(core_app.state.prompt_service_update_requests) == 1
    assert core_app.state.prompt_service_update_requests[0]["prompt_id"] == "prompt.email.classifier"
    assert body["updates"][0]["prompt_id"] == "prompt.email.classifier"


@pytest.mark.asyncio
async def test_runtime_sync_prompts_can_run_review_due_migration(config, core_client_factory):
    core_app = build_core_app()
    core_app.state.prompt_services["prompt.email.classifier"] = {
        "prompt_id": "prompt.email.classifier",
        "service_id": "node-email",
        "prompt_name": "Email Classifier",
        "status": "active",
        "current_version": "v1.1",
        "versions": ["v1.1"],
    }
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/prompts/sync",
            json={"target_api_base_url": "http://10.0.0.100:9002", "review_due_migration": True},
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["review_due_migration_result"]["migrated_count"] >= 1
    assert len(core_app.state.prompt_service_review_due_migration_requests) == 1
    assert service.state.runtime_prompt_review_due_migration_target_api_base_url == "http://10.0.0.100:9002"
    assert service.state.runtime_prompt_review_due_migration_result["migrated_count"] >= 1


@pytest.mark.asyncio
async def test_runtime_review_prompt_posts_review_request(config, core_client_factory):
    core_app = build_core_app()
    core_app.state.prompt_services["prompt.email.classifier"] = {
        "prompt_id": "prompt.email.classifier",
        "service_id": "node-email",
        "prompt_name": "Email Classifier",
        "status": "review_due",
        "current_version": "v1.1",
        "versions": ["v1.1"],
    }
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/prompts/review",
            json={
                "target_api_base_url": "http://10.0.0.100:9002",
                "prompt_id": "prompt.email.classifier",
                "review_status": "approved",
                "reason": "Reviewed during runtime prompt alignment.",
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["review_result"]["prompt_id"] == "prompt.email.classifier"
    assert len(core_app.state.prompt_service_review_requests) == 1
    assert core_app.state.prompt_service_review_requests[0]["prompt_id"] == "prompt.email.classifier"
    assert core_app.state.prompt_service_review_requests[0]["review_status"] == "approved"


@pytest.mark.asyncio
async def test_weekly_prompt_sync_runs_once_per_week_slot(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.runtime_prompt_sync_target_api_base_url = "http://10.0.0.100:9002"

    await service._run_weekly_prompt_sync_if_due()
    await service._run_weekly_prompt_sync_if_due()

    await service.stop()

    assert len(core_app.state.prompt_service_registration_requests) == 3
    assert service.state.runtime_prompt_sync_weekly_slot_key is not None


@pytest.mark.asyncio
async def test_runtime_execute_email_classifier_posts_normalized_email(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    older_unknown = GmailStoredMessage(
        account_id="primary",
        message_id="unknown-older",
        subject="Older",
        sender="Older Sender <older@example.com>",
        recipients=["primary@example.com"],
        snippet="older unknown body",
        received_at=datetime(2026, 4, 2, 10, 0, 0).astimezone(),
        local_label="unknown",
        local_label_confidence=0.2,
    )
    newest_unknown = GmailStoredMessage(
        account_id="primary",
        message_id="unknown-newest",
        subject="Newest",
        sender="Newest Sender <newest@example.com>",
        recipients=["primary@example.com"],
        snippet="please classify newest unknown",
        received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
        local_label="unknown",
        local_label_confidence=0.1,
    )
    classified_newer = GmailStoredMessage(
        account_id="primary",
        message_id="classified-newer",
        subject="Already known",
        sender="Known Sender <known@example.com>",
        recipients=["primary@example.com"],
        snippet="already classified",
        received_at=datetime(2026, 4, 2, 13, 0, 0).astimezone(),
        local_label="marketing",
        local_label_confidence=0.95,
    )
    adapter.message_store.upsert_messages([older_unknown, newest_unknown, classified_newer])
    adapter.message_store.upsert_sender_reputation(
        GmailSenderReputationRecord(
            account_id="primary",
            entity_type="email",
            sender_value="newest@example.com",
            sender_email="newest@example.com",
            sender_domain="example.com",
            reputation_state="blocked",
            rating=-4.0,
            inputs=GmailSenderReputationInputs(
                message_count=2,
                spamhaus_listed_count=1,
            ),
        )
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-email-classifier",
            json={
                "target_api_base_url": "http://10.0.0.100:9002",
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["execution"]["status"] == "completed"
    assert body["message_id"] == "unknown-newest"
    assert len(core_app.state.execution_direct_requests) == 1
    execution_request = core_app.state.execution_direct_requests[0]
    assert execution_request["prompt_id"] == "prompt.email.classifier"
    assert execution_request["prompt_version"] == service._load_runtime_prompt_definition("prompt.email.classifier")["version"]
    assert execution_request["task_family"] == "task.classification"
    assert execution_request["requested_by"] == "node-email"
    assert execution_request["service_id"] == "node-email"
    assert execution_request["customer_id"] == "local-user"
    assert execution_request["timeout_s"] == 60
    assert execution_request["inputs"]["text"] == (
        normalize_email_for_classifier(
            newest_unknown,
            my_addresses=["primary@example.com"],
        )
        + "\n"
        + "sender_reputation_state: blocked\n"
        + "sender_reputation_rating: -4.0\n"
        + "sender_reputation_messages: 2\n"
        + "sender_reputation_spamhaus_listed: 1"
    )
    assert execution_request["inputs"]["json_schema"] == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {
                "type": "string",
                "enum": [
                    "action_required",
                    "direct_human",
                    "financial",
                    "order",
                    "invoice",
                    "shipment",
                    "security",
                    "system",
                    "newsletter",
                    "marketing",
                    "unknown",
                ],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "rationale": {
                "type": "string",
            },
        },
        "required": ["label", "confidence", "rationale"],
    }


@pytest.mark.asyncio
async def test_runtime_execute_latest_email_action_decision_uses_newest_actionable_message(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    older_action = GmailStoredMessage(
        account_id="primary",
        message_id="action-older",
        subject="Older action",
        sender="Action Sender <action@example.com>",
        recipients=["primary@example.com"],
        snippet="older action mail",
        received_at=datetime(2026, 4, 2, 8, 0, 0).astimezone(),
        local_label="action_required",
        local_label_confidence=0.91,
    )
    newest_order = GmailStoredMessage(
        account_id="primary",
        message_id="order-newest",
        subject="Newest order",
        sender="Order Sender <order@example.com>",
        recipients=["primary@example.com"],
        snippet="newest order mail",
        received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
        local_label="order",
        local_label_confidence=0.96,
    )
    adapter.message_store.upsert_messages([older_action, newest_order])
    google_app = FastAPI()

    @google_app.get("/messages/{message_id}")
    async def get_full_message(message_id: str):
        assert message_id == "order-newest"
        return {
            "id": "order-newest",
            "threadId": "thread-1",
            "snippet": "Amazon order",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Order Sender <order@example.com>"},
                    {"name": "To", "value": "primary@example.com"},
                    {"name": "Subject", "value": "Newest order"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": "RnVsbCBlbWFpbCBib2R5IGZvciBhY3Rpb24gZGVjaXNpb24u"
                        },
                    },
                    {
                        "mimeType": "text/html",
                        "body": {
                            "data": "PGRpdj48cD5GdWxsIGVtYWlsIGJvZHkgPGI+Zm9yPC9iPiBhY3Rpb24gZGVjaXNpb24uPC9wPjwvZGl2Pg=="
                        },
                    }
                ],
            },
        }

    adapter.mailbox_client._client = httpx.AsyncClient(transport=ASGITransport(app=google_app), timeout=10.0)
    adapter.mailbox_client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-latest-email-action-decision",
            json={
                "target_api_base_url": "http://10.0.0.100:9002",
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["message_id"] == "order-newest"
    assert body["classification_label"] == "order"
    assert body["action_decision"]["summary"] == "Email needs a user response soon."
    saved = adapter.message_store.get_message("primary", "order-newest")
    assert saved is not None
    assert saved.action_decision_raw_response is not None
    assert saved.action_decision_raw_response["prompt_version"] == "v1.6"
    assert saved.action_decision_raw_response["validation_error"] is None
    assert len(core_app.state.execution_direct_requests) == 1
    execution_request = core_app.state.execution_direct_requests[0]
    assert execution_request["prompt_id"] == "prompt.email.action_decision"
    assert execution_request["prompt_version"] == "v1.6"
    assert execution_request["inputs"]["message_id"] == "order-newest"
    assert execution_request["inputs"]["text"] == (
        "subject: Newest order\nmail body:\nFull email body for action decision.\n"
        "mail html:\n<div><p>Full email body <b>for</b> action decision.</p></div>"
    )
    assert execution_request["inputs"]["body_text"] == "Full email body for action decision."
    assert execution_request["inputs"]["body_html"] == "<div><p>Full email body <b>for</b> action decision.</p></div>"


@pytest.mark.asyncio
async def test_runtime_settings_can_disable_ai_calls(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/runtime/settings", json={"ai_calls_enabled": False})

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["runtime_task_state"]["ai_calls_enabled"] is False
    assert service.state.runtime_task_state["ai_calls_enabled"] is False


@pytest.mark.asyncio
async def test_runtime_execute_email_classifier_rejects_when_ai_calls_disabled(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    service._save_runtime_task_state(ai_calls_enabled=False)
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="unknown-disabled",
                subject="Disabled",
                sender="Disabled Sender <disabled@example.com>",
                recipients=["primary@example.com"],
                snippet="do not send",
                received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
                local_label="unknown",
                local_label_confidence=0.1,
            )
        ]
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-email-classifier",
            json={"target_api_base_url": "http://10.0.0.100:9002"},
        )

    await service.stop()

    assert response.status_code == 400
    assert response.json()["detail"] == "AI calls are disabled in Runtime Settings."
    assert len(core_app.state.execution_direct_requests) == 0
    assert service.state.runtime_task_state["request_status"] == "failed"
    assert service.state.runtime_task_state["ai_calls_enabled"] is False


@pytest.mark.asyncio
async def test_runtime_execute_latest_email_action_decision_seeds_tracked_order_record(config, core_client_factory):
    core_app = build_core_app()
    core_app.state.action_decision_output_override = {
        "primary_label": "ORDER",
        "summary": "Amazon order update.",
        "urgency": "normal",
        "confidence": 0.98,
        "recommended_actions": [
            {
                "action": "track_shipment",
                "confidence": 0.99,
                "reason": "Shipment tracking is available.",
            },
            {
                "action": "notify",
                "confidence": 0.77,
                "reason": "The order update is useful to surface.",
            },
        ],
        "tracking_signals": {
            "is_shipment_related": True,
            "current_status": "arriving overnight 4 AM - 8 AM",
            "seller": "amazon",
            "carrier": "amazon",
            "order_number": "112-8876120-3805015",
            "tracking_number": "TBA11288761203805015",
        },
        "calendar_signals": {
            "has_calendar_invite": False,
            "has_meeting_request": False,
            "time_mentions": [],
        },
        "time_signals": {
            "is_time_sensitive": True,
            "deadline_mentions": [],
            "time_window_mentions": ["overnight 4 AM - 8 AM"],
        },
        "sender_signal": {
            "trust_hint": "trusted",
            "reasons": ["Official Amazon order email."],
        },
        "human_review_required": False,
    }
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    actionable = GmailStoredMessage(
        account_id="primary",
        message_id="order-track-seed",
        subject="Amazon shipment update",
        sender="Amazon <ship-confirm@amazon.com>",
        recipients=["primary@example.com"],
        snippet="Shipment arriving overnight.",
        received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
        local_label="order",
        local_label_confidence=0.96,
    )
    adapter.message_store.upsert_messages([actionable])
    google_app = FastAPI()

    @google_app.get("/messages/{message_id}")
    async def get_full_message(message_id: str):
        return {
            "id": message_id,
            "threadId": "thread-1",
            "snippet": "Amazon order update",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Amazon <ship-confirm@amazon.com>"},
                    {"name": "To", "value": "primary@example.com"},
                    {"name": "Subject", "value": "Amazon shipment update"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": "RnVsbCBlbWFpbCBib2R5IGZvciBhY3Rpb24gZGVjaXNpb24u"
                        },
                    }
                ],
            },
        }

    adapter.mailbox_client._client = httpx.AsyncClient(transport=ASGITransport(app=google_app), timeout=10.0)
    adapter.mailbox_client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-latest-email-action-decision",
            json={"target_api_base_url": "http://10.0.0.100:9002"},
        )

    tracked_orders = adapter.message_store.list_shipment_records("primary")
    await service.stop()

    assert response.status_code == 200
    assert len(tracked_orders) == 1
    assert tracked_orders[0].record_id == "order:112-8876120-3805015"
    assert tracked_orders[0].seller == "amazon"
    assert tracked_orders[0].carrier == "amazon"
    assert tracked_orders[0].domain == "amazon.com"
    assert tracked_orders[0].order_number == "112-8876120-3805015"
    assert tracked_orders[0].tracking_number == "TBA11288761203805015"
    assert tracked_orders[0].last_known_status == "arriving overnight 4 AM - 8 AM"


@pytest.mark.asyncio
async def test_runtime_execute_latest_email_action_decision_marks_no_tracking_orders_as_ordered(config, core_client_factory):
    core_app = build_core_app()
    core_app.state.action_decision_output_override = {
        "primary_label": "ORDER",
        "summary": "Amazon order confirmation.",
        "urgency": "normal",
        "confidence": 0.95,
        "recommended_actions": [
            {
                "action": "notify",
                "confidence": 0.8,
                "reason": "Useful confirmation for the user.",
            }
        ],
        "tracking_signals": {
            "is_shipment_related": False,
            "current_status": None,
            "seller": "amazon",
            "carrier": None,
            "order_number": "112-0000000-0000000",
            "tracking_number": None,
        },
        "calendar_signals": {
            "has_calendar_invite": False,
            "has_meeting_request": False,
            "time_mentions": [],
        },
        "time_signals": {
            "is_time_sensitive": False,
            "deadline_mentions": [],
            "time_window_mentions": [],
        },
        "sender_signal": {
            "trust_hint": "trusted",
            "reasons": ["Official Amazon order confirmation."],
        },
        "human_review_required": False,
    }
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    actionable = GmailStoredMessage(
        account_id="primary",
        message_id="order-confirmation",
        subject="Amazon order placed",
        sender="Amazon <auto-confirm@amazon.com>",
        recipients=["primary@example.com"],
        snippet="Your order has been placed.",
        received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
        local_label="order",
        local_label_confidence=0.96,
    )
    adapter.message_store.upsert_messages([actionable])
    google_app = FastAPI()

    @google_app.get("/messages/{message_id}")
    async def get_full_message(message_id: str):
        return {
            "id": message_id,
            "threadId": "thread-1",
            "snippet": "Amazon order confirmation",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Amazon <auto-confirm@amazon.com>"},
                    {"name": "To", "value": "primary@example.com"},
                    {"name": "Subject", "value": "Amazon order placed"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": "RnVsbCBlbWFpbCBib2R5IGZvciBvcmRlciBjb25maXJtYXRpb24u"
                        },
                    }
                ],
            },
        }

    adapter.mailbox_client._client = httpx.AsyncClient(transport=ASGITransport(app=google_app), timeout=10.0)
    adapter.mailbox_client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-latest-email-action-decision",
            json={"target_api_base_url": "http://10.0.0.100:9002"},
        )

    tracked_orders = adapter.message_store.list_shipment_records("primary")
    await service.stop()

    assert response.status_code == 200
    assert len(tracked_orders) == 1
    assert tracked_orders[0].record_id == "order:112-0000000-0000000"
    assert tracked_orders[0].tracking_number is None
    assert tracked_orders[0].last_known_status == "ordered"


@pytest.mark.asyncio
async def test_runtime_execute_latest_email_action_decision_rejects_partial_output(config, core_client_factory):
    core_app = build_core_app()
    core_app.state.action_decision_output_override = {
        "primary_label": "SHIPMENT",
        "recommended_actions": [
            {
                "action": "track_shipment",
                "confidence": 0.98,
                "reason": "Tracking is appropriate.",
            }
        ],
    }
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    actionable = GmailStoredMessage(
        account_id="primary",
        message_id="order-partial",
        subject="Partial order",
        sender="Order Sender <order@example.com>",
        recipients=["primary@example.com"],
        snippet="partial action decision mail",
        received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
        local_label="order",
        local_label_confidence=0.96,
    )
    adapter.message_store.upsert_messages([actionable])
    google_app = FastAPI()

    @google_app.get("/messages/{message_id}")
    async def get_full_message(message_id: str):
        return {
            "id": message_id,
            "threadId": "thread-1",
            "snippet": "Amazon order",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Order Sender <order@example.com>"},
                    {"name": "To", "value": "primary@example.com"},
                    {"name": "Subject", "value": "Partial order"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": "UGFydGlhbCBhY3Rpb24gZGVjaXNpb24gYm9keS4="
                        },
                    }
                ],
            },
        }

    adapter.mailbox_client._client = httpx.AsyncClient(transport=ASGITransport(app=google_app), timeout=10.0)
    adapter.mailbox_client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-latest-email-action-decision",
            json={
                "target_api_base_url": "http://10.0.0.100:9002",
            },
        )

    saved = adapter.message_store.get_message("primary", "order-partial")
    await service.stop()

    assert response.status_code == 500
    assert saved is not None
    assert saved.action_decision_payload is None
    assert saved.action_decision_raw_response is not None
    assert saved.action_decision_raw_response["prompt_version"] == "v1.6"
    assert "missing required field summary" in str(saved.action_decision_raw_response["validation_error"])


@pytest.mark.asyncio
async def test_runtime_execute_email_classifier_batch_registers_prompt_and_classifies_unknowns(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="unknown-1",
                subject="First unknown",
                sender="First Sender <first@example.com>",
                recipients=["primary@example.com"],
                snippet="please classify first",
                received_at=datetime(2026, 4, 2, 10, 0, 0).astimezone(),
                local_label="unknown",
                local_label_confidence=0.1,
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="unknown-2",
                subject="Second unknown",
                sender="Second Sender <second@example.com>",
                recipients=["primary@example.com"],
                snippet="please classify second",
                received_at=datetime(2026, 4, 2, 11, 0, 0).astimezone(),
                local_label="unknown",
                local_label_confidence=0.2,
            ),
        ]
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-email-classifier-batch",
            json={
                "target_api_base_url": "http://10.0.0.100:9002",
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["batch_size"] == 2
    assert body["local_processed"] == 0
    assert body["local_classified"] == 0
    assert body["ai_total"] == 2
    assert body["ai_attempted"] == 2
    assert body["ai_completed"] == 2
    assert len(core_app.state.prompt_service_registration_requests) == 0
    assert len(core_app.state.execution_direct_requests) == 2

    updated_messages = {message.message_id: message for message in adapter.message_store.list_messages("primary", limit=10)}
    assert updated_messages["unknown-1"].local_label == "marketing"
    assert updated_messages["unknown-2"].local_label == "marketing"
    assert service.state.runtime_task_state["request_status"] == "executed"
    assert service.state.runtime_task_state["last_step"] == "execute_batch"


@pytest.mark.asyncio
async def test_runtime_execute_email_classifier_batch_skips_ai_when_disabled(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    service._save_runtime_task_state(ai_calls_enabled=False)
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="unknown-1",
                subject="First unknown",
                sender="First Sender <first@example.com>",
                recipients=["primary@example.com"],
                snippet="please classify first",
                received_at=datetime(2026, 4, 2, 10, 0, 0).astimezone(),
                local_label="unknown",
                local_label_confidence=0.1,
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="unknown-2",
                subject="Second unknown",
                sender="Second Sender <second@example.com>",
                recipients=["primary@example.com"],
                snippet="please classify second",
                received_at=datetime(2026, 4, 2, 11, 0, 0).astimezone(),
                local_label="unknown",
                local_label_confidence=0.2,
            ),
        ]
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/runtime/execute-email-classifier-batch",
            json={"target_api_base_url": "http://10.0.0.100:9002"},
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["batch_size"] == 2
    assert body["local_processed"] == 0
    assert body["local_classified"] == 0
    assert body["ai_total"] == 2
    assert body["ai_attempted"] == 0
    assert body["ai_completed"] == 0
    assert body["ai_calls_enabled"] is False
    assert len(core_app.state.execution_direct_requests) == 0
    assert service.state.runtime_task_state["request_status"] == "executed"
    assert service.state.runtime_task_state["last_step"] == "execute_batch"
    assert service.state.runtime_task_state["ai_calls_enabled"] is False


def test_runtime_classifier_output_normalization_helpers(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    parsed = service._parse_classifier_output(
        {
            "result": {
                "category": "Direct Human",
                "score": "91%",
                "rationale": "Looks like a person-to-person email.",
            }
        }
    )

    assert parsed is not None
    assert service._normalize_classifier_label(parsed.get("category")) == GmailTrainingLabel.DIRECT_HUMAN
    assert service._normalize_classifier_confidence(parsed.get("score")) == 0.91


def test_runtime_action_decision_output_parser_accepts_string_wrapped_json(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    parsed = service._parse_action_decision_output(
        {
            "response": {
                "output_text": (
                    "{\"primary_label\":\"ORDER\",\"summary\":\"Order update\",\"urgency\":\"normal\","
                    "\"recommended_actions\":[{\"action\":\"notify\",\"confidence\":0.9,\"reason\":\"Useful order update\"}],"
                    "\"human_review_required\":false}"
                )
            }
        }
    )

    assert parsed is not None
    assert parsed["primary_label"] == "ORDER"
    assert parsed["summary"] == "Order update"


def test_runtime_action_decision_schema_validation_rejects_partial_payload(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    prompt_definition = service._load_runtime_prompt_definition("prompt.email.action_decision")
    prompt_runtime = prompt_definition.get("node_runtime")

    assert isinstance(prompt_runtime, dict)
    assert isinstance(prompt_runtime.get("json_schema"), dict)

    validated = service._validate_action_decision_payload(
        {
            "primary_label": "SHIPMENT",
            "recommended_actions": [
                {
                    "action": "track_shipment",
                    "confidence": 0.98,
                    "reason": "Tracking is appropriate.",
                }
            ],
        },
        prompt_runtime["json_schema"],
    )

    assert validated is None


@pytest.mark.asyncio
async def test_ui_bootstrap_restores_persisted_runtime_task_state(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.runtime_task_state = {
        "request_status": "authorized",
        "last_step": "authorize",
        "detail": "Saved runtime authorize state.",
        "preview_response": {"detail": "previewed"},
        "resolve_response": {"selected_service_id": "svc-1"},
        "authorize_response": {"grant_id": "grant-1", "token": "tok-1"},
        "execution_response": None,
        "usage_summary_response": None,
        "started_at": "2026-04-02T20:00:00+00:00",
        "updated_at": "2026-04-02T20:01:00+00:00",
    }
    service.state_store.save(service.state)
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/node/bootstrap")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["runtime_task_state"]["request_status"] == "authorized"
    assert body["runtime_task_state"]["resolve_response"]["selected_service_id"] == "svc-1"
    assert body["runtime_task_state"]["authorize_response"]["grant_id"] == "grant-1"


@pytest.mark.asyncio
async def test_ui_bootstrap_exposes_scheduled_tasks(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.trust_material = TrustMaterial(
        node_id="node-1",
        node_type="email-node",
        paired_core_id="core-1",
        node_trust_token="trust-secret",
        operational_mqtt_identity="mqtt-user",
        operational_mqtt_token="mqtt-secret",
        operational_mqtt_host="127.0.0.1",
        operational_mqtt_port=1883,
    )
    service.state.runtime_prompt_sync_target_api_base_url = "http://10.0.0.100:9002"
    service.state.runtime_prompt_sync_weekly_slot_key = "2026-W14"
    service.state.runtime_prompt_sync_last_scheduled_at = datetime(2026, 4, 3, 8, 0, 0).astimezone()
    service.state.runtime_monthly_authorize_slot_key = "2026-04"
    service.state.runtime_monthly_authorize_last_run_at = datetime(2026, 4, 1, 0, 1, 0).astimezone()
    service.state.gmail_hourly_batch_classification_slot_key = "2026-04-03T08:00:00+00:00"
    service.state.gmail_hourly_batch_classification_last_run_at = datetime(2026, 4, 3, 8, 1, 0).astimezone()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/node/bootstrap")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    task_ids = {item["task_id"] for item in body["scheduled_tasks"]}
    assert "gmail_fetch_yesterday" in task_ids
    assert "gmail_fetch_today" in task_ids
    assert "gmail_fetch_last_hour" in task_ids
    assert "gmail_hourly_batch_classification" in task_ids
    assert "runtime_prompt_sync_weekly" in task_ids
    assert "runtime_monthly_resolve_authorize" in task_ids
    legend_names = {item["name"] for item in body["scheduled_task_legend"]}
    assert "daily" in legend_names
    assert "weekly" in legend_names
    assert "monthly" in legend_names
    assert "on_start" in legend_names
    weekly_legend = next(item for item in body["scheduled_task_legend"] if item["name"] == "weekly")
    assert weekly_legend["detail"] == "Monday 00:01"
    monthly_legend = next(item for item in body["scheduled_task_legend"] if item["name"] == "monthly")
    assert monthly_legend["detail"] == "First day of each month at 00:01"
    on_start_legend = next(item for item in body["scheduled_task_legend"] if item["name"] == "on_start")
    assert on_start_legend["detail"] == "Runs once after full operational readiness"
    prompt_sync = next(item for item in body["scheduled_tasks"] if item["task_id"] == "runtime_prompt_sync_weekly")
    assert prompt_sync["last_slot_key"] == "2026-W14"
    assert prompt_sync["last_execution_at"] is not None
    assert prompt_sync["schedule_name"] == "weekly"
    assert prompt_sync["schedule_detail"] == "Monday 00:01"
    prompt_sync_next = datetime.fromisoformat(prompt_sync["next_execution_at"])
    assert prompt_sync_next.weekday() == 0
    assert prompt_sync_next.hour == 0
    assert prompt_sync_next.minute == 1
    monthly_runtime = next(item for item in body["scheduled_tasks"] if item["task_id"] == "runtime_monthly_resolve_authorize")
    assert monthly_runtime["last_slot_key"] == "2026-04"
    assert monthly_runtime["last_execution_at"] is not None
    assert monthly_runtime["schedule_name"] == "monthly"
    assert monthly_runtime["schedule_detail"] == "First day of each month at 00:01"
    monthly_next = datetime.fromisoformat(monthly_runtime["next_execution_at"])
    assert monthly_next.day == 1
    assert monthly_next.hour == 0
    assert monthly_next.minute == 1


@pytest.mark.asyncio
async def test_ui_bootstrap_exposes_tracked_orders(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    gmail_adapter = service.provider_registry.get_provider("gmail")
    gmail_adapter.message_store.upsert_shipment_record(
        GmailShipmentRecord(
            account_id="primary",
            record_id="ship-1",
            seller="amazon",
            carrier="fedex",
            order_number="111-1234567-1234567",
            tracking_number="449044304137821",
            domain="amazon.com",
            last_known_status="delivered",
            last_seen_at=datetime(2026, 4, 3, 11, 0, 0).astimezone(),
            status_updated_at=datetime(2026, 4, 3, 11, 0, 0).astimezone(),
            updated_at=datetime(2026, 4, 3, 11, 5, 0).astimezone(),
        )
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/node/bootstrap")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert len(body["tracked_orders"]) == 1
    tracked = body["tracked_orders"][0]
    assert tracked["account_id"] == "primary"
    assert tracked["seller"] == "amazon"
    assert tracked["carrier"] == "fedex"
    assert tracked["order_number"] == "111-1234567-1234567"
    assert tracked["tracking_number"] == "449044304137821"
    assert tracked["last_known_status"] == "delivered"


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
            unread_last_hour_count=2,
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
    assert body["accounts"][0]["mailbox_status"]["unread_last_hour_count"] == 2
    assert body["accounts"][0]["classification_summary"]["classified_count"] == 0


@pytest.mark.asyncio
async def test_gmail_status_api_exposes_classification_summary(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    if service.gmail_status_task is not None:
        service.gmail_status_task.cancel()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="manual-1",
                subject="Manual label",
                sender="manual@example.com",
                recipients=["primary@example.com"],
                snippet="manual",
                received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="high-1",
                subject="High confidence",
                sender="high@example.com",
                recipients=["primary@example.com"],
                snippet="high",
                received_at=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
            ),
        ]
    )
    adapter.message_store.update_local_classification(
        "primary",
        "manual-1",
        label=GmailTrainingLabel.DIRECT_HUMAN,
        confidence=1.0,
        manual_classification=True,
    )
    adapter.message_store.update_local_classification(
        "primary",
        "high-1",
        label=GmailTrainingLabel.MARKETING,
        confidence=0.95,
        manual_classification=False,
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/gmail/status")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["accounts"][0]["classification_summary"]["classified_count"] == 2
    assert body["accounts"][0]["classification_summary"]["manual_count"] == 1
    assert body["accounts"][0]["classification_summary"]["high_confidence_count"] == 1


@pytest.mark.asyncio
async def test_gmail_status_api_exposes_model_training_status(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    if service.gmail_status_task is not None:
        service.gmail_status_task.cancel()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )

    class FakeTrainingModelStore:
        def status(self):
            return {
                "trained": True,
                "trained_at": "2026-04-02T12:10:00-07:00",
                "sample_count": 12,
                "train_count": 9,
                "test_count": 3,
                "detail": "trained in test",
            }

    adapter.training_model_store = FakeTrainingModelStore()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/gmail/status")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["accounts"][0]["model_status"]["trained"] is True
    assert body["accounts"][0]["model_status"]["trained_at"] == "2026-04-02T12:10:00-07:00"


@pytest.mark.asyncio
async def test_gmail_status_api_exposes_sender_reputation_summary(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    if service.gmail_status_task is not None:
        service.gmail_status_task.cancel()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                subject="Review",
                sender="Alerts <alerts@example.com>",
                recipients=["primary@example.com"],
                snippet="Please review",
                received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
            )
        ]
    )
    adapter.message_store.update_local_classification(
        "primary",
        "msg-1",
        label=GmailTrainingLabel.ACTION_REQUIRED,
        confidence=1.0,
        manual_classification=True,
    )
    await adapter.refresh_sender_reputations("primary")
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/gmail/status")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    sender_reputation = body["accounts"][0]["sender_reputation"]
    assert sender_reputation["total_count"] == 2
    assert sender_reputation["records"][0]["sender_value"] in {"alerts@example.com", "example.com"}
    assert sender_reputation["by_state"]["neutral"] == 2


@pytest.mark.asyncio
async def test_gmail_sender_reputation_refresh_api_recomputes_records(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Alerts <alerts@example.com>",
                recipients=["primary@example.com"],
                subject="Need review",
                snippet="Please review",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
            )
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    adapter.message_store.update_local_classification(
        "primary",
        "msg-1",
        label=GmailTrainingLabel.ACTION_REQUIRED,
        confidence=1.0,
        manual_classification=True,
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/gmail/reputation/refresh")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["refreshed_count"] == 2
    assert body["summary"]["total_count"] == 2


@pytest.mark.asyncio
async def test_gmail_sender_reputation_manual_rating_api_updates_record(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Alerts <alerts@mail.example.com>",
                recipients=["primary@example.com"],
                subject="Need review",
                snippet="Please review",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
            )
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    adapter.message_store.update_local_classification(
        "primary",
        "msg-1",
        label=GmailTrainingLabel.ACTION_REQUIRED,
        confidence=1.0,
        manual_classification=True,
    )
    await adapter.refresh_sender_reputations("primary")
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/gmail/reputation/manual-rating",
            json={
                "entity_type": "business_domain",
                "sender_value": "example.com",
                "manual_rating": -4.0,
                "note": "Operator blocked",
            },
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["record"]["entity_type"] == "business_domain"
    assert body["record"]["sender_value"] == "example.com"
    assert body["record"]["manual_rating"] == -4.0
    assert body["record"]["manual_rating_note"] == "Operator blocked"
    assert body["record"]["rating"] == -3.0


def build_google_fetch_test_app():
    app = build_core_app()

    @app.get("/messages")
    async def list_messages():
        return {"messages": [{"id": "msg-1"}]}

    @app.get("/messages/{message_id}")
    async def get_message(message_id: str):
        return {
            "id": message_id,
            "threadId": "thread-1",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "hello world",
            "internalDate": "1775121600000",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Sender <sender@example.com>"},
                    {"name": "To", "value": "primary@example.com"},
                    {"name": "Subject", "value": "Hello"},
                ]
            },
        }

    return app


@pytest.mark.asyncio
async def test_gmail_fetch_api_stores_messages_for_requested_window(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    if service.gmail_status_task is not None:
        service.gmail_status_task.cancel()

    adapter = service.provider_registry.get_provider("gmail")
    GmailProviderConfigStore(config.runtime_dir).save(
        GmailOAuthConfig(enabled=True, client_id="client-id", client_secret_ref="secret", redirect_uri="https://hexe-ai.com/google/gmail/callback")
    )
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.token_store.save_token(
        "primary",
        GmailTokenRecord(
            account_id="primary",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
        ),
    )
    adapter.mailbox_client = GmailMailboxClient(transport=ASGITransport(app=build_google_fetch_test_app()))
    adapter.mailbox_client.quota_tracker = adapter.quota_tracker
    adapter.mailbox_client.MESSAGES_ENDPOINT = "http://google.test/messages"
    adapter.mailbox_client.MESSAGE_ENDPOINT_TEMPLATE = "http://google.test/messages/{message_id}"
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/gmail/fetch/last_hour")
        status_response = await client.get("/api/gmail/status")

    await service.stop()

    assert response.status_code == 200
    assert response.json()["window"] == "last_hour"
    assert response.json()["fetched_count"] == 1
    assert response.json()["summary"]["total_count"] == 1

    assert status_response.status_code == 200
    assert status_response.json()["accounts"][0]["message_store"]["total_count"] == 1
    assert status_response.json()["accounts"][0]["mailbox_status"]["unread_inbox_count"] == 1
    assert status_response.json()["accounts"][0]["mailbox_status"]["unread_today_count"] == 1
    assert status_response.json()["accounts"][0]["mailbox_status"]["unread_last_hour_count"] == 1
    assert status_response.json()["accounts"][0]["quota_usage"]["used_last_minute"] == 10
    assert status_response.json()["accounts"][0]["quota_usage"]["remaining_last_minute"] == 14990


@pytest.mark.asyncio
async def test_gmail_spamhaus_check_api_marks_stored_messages(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Sender <sender@example.com>",
                received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
            )
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    adapter.message_store.upsert_spamhaus_check(
        GmailSpamhausCheck(
            account_id="primary",
            message_id="msg-1",
            sender_email="sender@example.com",
            sender_domain="example.com",
            checked=True,
            listed=False,
            status="clean",
        ),
        now=datetime(2026, 4, 2, 12, 6, 0).astimezone(),
    )

    class FakeSpamhausChecker:
        async def check_sender(self, *, account_id: str, message_id: str, sender: str | None):
            return GmailSpamhausCheck(
                account_id=account_id,
                message_id=message_id,
                sender_email="sender@example.com",
                sender_domain="example.com",
                checked=True,
                listed=True,
                status="listed",
                detail="listed in test",
            )

    adapter.spamhaus_checker = FakeSpamhausChecker()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/gmail/spamhaus/check")
        status_response = await client.get("/api/gmail/status")

    await service.stop()

    assert response.status_code == 200
    assert response.json()["checked_count"] == 1
    assert response.json()["listed_count"] == 1
    assert status_response.status_code == 200
    assert status_response.json()["accounts"][0]["spamhaus"]["checked_count"] == 1
    assert status_response.json()["accounts"][0]["spamhaus"]["listed_count"] == 1
    assert status_response.json()["accounts"][0]["spamhaus"]["pending_count"] == 0


@pytest.mark.asyncio
async def test_gmail_training_api_returns_manual_batch_and_saves_labels(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Sender <sender@example.com>",
                recipients=["primary@example.com"],
                subject="Re: Please review",
                snippet="Please review and unsubscribe if not needed",
                label_ids=["INBOX", "UNREAD"],
                received_at=datetime(2026, 4, 2, 12, 0, 0).astimezone(),
                raw_payload='{"payload":{"headers":[{"name":"To","value":"primary@example.com"},{"name":"List-Unsubscribe","value":"<mailto:test@example.com>"}]}}',
            )
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        batch_response = await client.post("/api/gmail/training/manual-batch")
        save_response = await client.post(
            "/api/gmail/training/manual-classify",
            json={"items": [{"message_id": "msg-1", "label": "direct_human", "confidence": 0.95}]},
        )

    await service.stop()

    assert batch_response.status_code == 200
    body = batch_response.json()
    assert body["count"] == 1
    assert "from: sender@example.com" in body["items"][0]["flat_text"]
    assert "is_reply=true" in body["items"][0]["flat_text"]
    assert "has_unsubscribe=true" in body["items"][0]["flat_text"]
    assert body["items"][0]["raw_text"].startswith("from: Sender <sender@example.com>")
    assert "subject: Re: Please review" in body["items"][0]["raw_text"]

    assert save_response.status_code == 200
    assert save_response.json()["saved_count"] == 1
    saved_message = adapter.message_store.list_messages("primary", limit=1)[0]
    assert saved_message.local_label == "direct_human"
    assert saved_message.local_label_confidence == 0.95
    assert saved_message.manual_classification is True


@pytest.mark.asyncio
async def test_gmail_training_api_supports_model_training_and_semi_auto_review(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="train-1",
                sender="Sender <sender@example.com>",
                recipients=["primary@example.com"],
                subject="Human follow up",
                snippet="Please review this directly",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="train-2",
                sender="Billing <billing@example.com>",
                recipients=["primary@example.com"],
                subject="Invoice ready",
                snippet="Your invoice is attached",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 13, 0, 0).astimezone(),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="predict-1",
                sender="Unknown <unknown@example.com>",
                recipients=["primary@example.com"],
                subject="Need attention",
                snippet="Please check this item",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 10, 0, 0).astimezone(),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="auto-1",
                sender="Deals <deals@example.com>",
                recipients=["primary@example.com"],
                subject="Big sale today",
                snippet="Limited offer just for you",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 9, 0, 0).astimezone(),
            ),
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    adapter.message_store.update_local_classification(
        "primary",
        "train-1",
        label=GmailTrainingLabel.DIRECT_HUMAN,
        confidence=1.0,
        manual_classification=True,
    )
    adapter.message_store.update_local_classification(
        "primary",
        "train-2",
        label=GmailTrainingLabel.INVOICE,
        confidence=1.0,
        manual_classification=True,
    )
    adapter.message_store.update_local_classification(
        "primary",
        "auto-1",
        label=GmailTrainingLabel.MARKETING,
        confidence=0.98,
        manual_classification=False,
    )
    for message_id in ["train-1", "train-2", "predict-1", "auto-1"]:
        adapter.message_store.upsert_spamhaus_check(
            GmailSpamhausCheck(
                account_id="primary",
                message_id=message_id,
                sender_email=f"{message_id}@example.com",
                sender_domain="example.com",
                checked=True,
                listed=False,
                status="clean",
            ),
            now=datetime(2026, 4, 2, 12, 6, 0).astimezone(),
        )

    class FakeTrainingModelStore:
        def __init__(self) -> None:
            self.trained = False

        def status(self):
            if not self.trained:
                return {
                    "trained": False,
                    "trained_at": None,
                    "sample_count": 0,
                    "class_counts": {},
                    "detail": "Model has not been trained yet.",
                }
            return {
                "trained": True,
                "trained_at": "2026-04-02T12:10:00-07:00",
                "sample_count": 2,
                "class_counts": {"direct_human": 1, "invoice": 1},
                "dataset_summary": {"included_count": 2},
                "detail": "trained in test",
            }

        def train_classifier(self, dataset, *, dataset_summary):
            assert len(dataset) == 2
            assert [row.message_id for row in dataset] == ["train-1", "train-2"]
            assert [row.label.value for row in dataset] == ["direct_human", "invoice"]
            assert dataset_summary.included_count == 2
            self.trained = True
            return self.status()

        def predict(self, texts, *, threshold):
            assert threshold == 0.6
            assert len(texts) == 1
            return [
                {
                    "predicted_label": "direct_human",
                    "predicted_confidence": 0.82,
                    "raw_predicted_label": "direct_human",
                }
            ]

    adapter.training_model_store = FakeTrainingModelStore()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        train_response = await client.post("/api/gmail/training/train-model")
        batch_response = await client.post("/api/gmail/training/semi-auto-batch")
        save_response = await client.post(
            "/api/gmail/training/semi-auto-review",
            json={
                "items": [
                    {
                        "message_id": "predict-1",
                        "selected_label": "financial",
                        "predicted_label": "direct_human",
                        "predicted_confidence": 0.82,
                    }
                ]
            },
        )

    await service.stop()

    assert train_response.status_code == 200
    assert train_response.json()["model_status"]["trained"] is True

    assert batch_response.status_code == 200
    batch_body = batch_response.json()
    assert batch_body["source"] == "semi_auto"
    assert batch_body["count"] == 1
    assert batch_body["items"][0]["predicted_label"] == "direct_human"
    assert batch_body["items"][0]["predicted_confidence"] == 0.82

    assert save_response.status_code == 200
    assert save_response.json()["saved_count"] == 1
    assert save_response.json()["manual_count"] == 1
    saved_message = next(message for message in adapter.message_store.list_messages("primary", limit=10) if message.message_id == "predict-1")
    assert saved_message.local_label == "financial"
    assert saved_message.local_label_confidence == 1.0
    assert saved_message.manual_classification is True


@pytest.mark.asyncio
async def test_gmail_training_api_supports_high_confidence_only_training(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="hi-1",
                sender="Promo <promo@example.com>",
                recipients=["primary@example.com"],
                subject="Great sale",
                snippet="Offer",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
                local_label="marketing",
                local_label_confidence=0.95,
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="lo-1",
                sender="Update <update@example.com>",
                recipients=["primary@example.com"],
                subject="System update",
                snippet="Info",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 11, 0, 0).astimezone(),
                local_label="system",
                local_label_confidence=0.85,
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="manual-1",
                sender="Person <person@example.com>",
                recipients=["primary@example.com"],
                subject="Please respond",
                snippet="Need your reply",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 10, 0, 0).astimezone(),
                local_label="direct_human",
                local_label_confidence=1.0,
                manual_classification=True,
            ),
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    for message_id in ["hi-1", "lo-1", "manual-1"]:
        adapter.message_store.upsert_spamhaus_check(
            GmailSpamhausCheck(
                account_id="primary",
                message_id=message_id,
                sender_email=f"{message_id}@example.com",
                sender_domain="example.com",
                checked=True,
                listed=False,
                status="clean",
            ),
            now=datetime(2026, 4, 2, 12, 6, 0).astimezone(),
        )

    class FakeTrainingModelStore:
        def train_classifier(self, dataset, *, dataset_summary):
            assert [row.message_id for row in dataset] == ["hi-1", "manual-1"]
            assert dataset_summary.included_count == 2
            return {
                "trained": True,
                "trained_at": "2026-04-02T12:10:00-07:00",
                "sample_count": 2,
                "train_count": 1,
                "test_count": 1,
                "class_counts": {"marketing": 1, "direct_human": 1},
                "detail": "trained in test",
            }

        def status(self):
            return {
                "trained": True,
                "trained_at": "2026-04-02T12:10:00-07:00",
                "sample_count": 2,
                "class_counts": {"marketing": 1, "direct_human": 1},
                "detail": "trained in test",
            }

    adapter.training_model_store = FakeTrainingModelStore()
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        train_response = await client.post("/api/gmail/training/train-model?minimum_confidence=0.92")

    await service.stop()

    assert train_response.status_code == 200
    assert train_response.json()["minimum_confidence"] == 0.92


@pytest.mark.asyncio
async def test_gmail_training_status_includes_manual_and_high_confidence_counts(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="manual-1",
                sender="Person <person@example.com>",
                recipients=["primary@example.com"],
                subject="Need review",
                snippet="Please review",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="high-1",
                sender="Deals <deals@example.com>",
                recipients=["primary@example.com"],
                subject="Big sale",
                snippet="Offer",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 11, 0, 0).astimezone(),
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="low-1",
                sender="Alerts <alerts@example.com>",
                recipients=["primary@example.com"],
                subject="Heads up",
                snippet="Notice",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 10, 0, 0).astimezone(),
            ),
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    adapter.message_store.update_local_classification(
        "primary",
        "manual-1",
        label=GmailTrainingLabel.DIRECT_HUMAN,
        confidence=1.0,
        manual_classification=True,
    )
    adapter.message_store.update_local_classification(
        "primary",
        "high-1",
        label=GmailTrainingLabel.MARKETING,
        confidence=0.95,
        manual_classification=False,
    )
    adapter.message_store.update_local_classification(
        "primary",
        "low-1",
        label=GmailTrainingLabel.SYSTEM,
        confidence=0.91,
        manual_classification=False,
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/gmail/training")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["classification_summary"]["manual_count"] == 1
    assert body["classification_summary"]["high_confidence_count"] == 1


@pytest.mark.asyncio
async def test_gmail_reputation_detail_api_exposes_record_and_recent_messages(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="msg-1",
                sender="Alerts <alerts@example.com>",
                recipients=["primary@example.com"],
                subject="Need review",
                snippet="Please review",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
            )
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    adapter.message_store.update_local_classification(
        "primary",
        "msg-1",
        label=GmailTrainingLabel.ACTION_REQUIRED,
        confidence=1.0,
        manual_classification=True,
    )
    adapter.message_store.upsert_spamhaus_check(
        GmailSpamhausCheck(
            account_id="primary",
            message_id="msg-1",
            sender_email="alerts@example.com",
            sender_domain="example.com",
            checked=True,
            listed=False,
            status="clean",
        ),
        now=datetime(2026, 4, 2, 12, 6, 0).astimezone(),
    )
    await adapter.refresh_sender_reputations("primary")
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/gmail/reputation/detail",
            params={"entity_type": "email", "sender_value": "alerts@example.com"},
        )

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["record"]["sender_value"] == "alerts@example.com"
    assert body["record"]["inputs"]["classification_positive_count"] == 1
    assert body["record"]["inputs"]["spamhaus_clean_count"] == 1
    assert body["related_message_count"] == 1
    assert body["recent_messages"][0]["message_id"] == "msg-1"


@pytest.mark.asyncio
async def test_gmail_training_api_supports_classified_label_batch(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="m1",
                sender="Promo <promo@example.com>",
                recipients=["primary@example.com"],
                subject="Great sale",
                snippet="Offer",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
                local_label="marketing",
                local_label_confidence=0.95,
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="m2",
                sender="Other <other@example.com>",
                recipients=["primary@example.com"],
                subject="Invoice",
                snippet="Bill",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 11, 0, 0).astimezone(),
                local_label="invoice",
                local_label_confidence=0.9,
            ),
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        batch_response = await client.post("/api/gmail/training/classified-batch?label=marketing")

    await service.stop()

    assert batch_response.status_code == 200
    body = batch_response.json()
    assert body["source"] == "classified_label"
    assert body["selected_label"] == "marketing"
    assert body["count"] == 1
    assert body["items"][0]["message_id"] == "m1"


@pytest.mark.asyncio
async def test_gmail_training_classified_batch_orders_newest_first(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    adapter = service.provider_registry.get_provider("gmail")
    adapter.account_store.save_account(
        adapter.state_machine.ensure_account("primary").model_copy(
            update={"status": "connected", "email_address": "primary@example.com"}
        )
    )
    adapter.message_store.upsert_messages(
        [
            GmailStoredMessage(
                account_id="primary",
                message_id="older",
                sender="Promo <promo@example.com>",
                recipients=["primary@example.com"],
                subject="Older sale",
                snippet="Offer",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 11, 0, 0).astimezone(),
                local_label="marketing",
                local_label_confidence=0.95,
            ),
            GmailStoredMessage(
                account_id="primary",
                message_id="newer",
                sender="Promo <promo@example.com>",
                recipients=["primary@example.com"],
                subject="Newer sale",
                snippet="Offer",
                label_ids=["INBOX"],
                received_at=datetime(2026, 4, 1, 12, 0, 0).astimezone(),
                local_label="marketing",
                local_label_confidence=0.97,
            ),
        ],
        now=datetime(2026, 4, 2, 12, 5, 0).astimezone(),
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        batch_response = await client.post("/api/gmail/training/classified-batch?label=marketing")

    await service.stop()

    assert batch_response.status_code == 200
    body = batch_response.json()
    assert [item["message_id"] for item in body["items"]] == ["newer", "older"]


@pytest.mark.asyncio
async def test_gmail_status_api_exposes_fetch_schedule_state(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    GmailFetchScheduleStore(config.runtime_dir).save_state(
        GmailFetchScheduleState(
            yesterday=GmailFetchWindowState(last_run_at=datetime(2026, 4, 2, 0, 1, 0), last_run_reason="scheduled", last_slot_key="2026-04-01"),
            today=GmailFetchWindowState(last_run_at=datetime(2026, 4, 2, 6, 0, 0), last_run_reason="manual", last_slot_key="2026-04-02:1"),
            last_hour=GmailFetchWindowState(last_run_at=datetime(2026, 4, 2, 7, 0, 0), last_run_reason="scheduled", last_slot_key="2026-04-02T07:00:00+00:00"),
        )
    )
    app = create_app(config=config, service=service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/gmail/status")

    await service.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["fetch_schedule"]["yesterday"]["last_run_reason"] == "scheduled"
    assert body["fetch_schedule"]["today"]["last_run_reason"] == "manual"


def test_gmail_fetch_schedule_state_accepts_auto_reason(runtime_dir):
    store = GmailFetchScheduleStore(runtime_dir)
    store.save_state(
        GmailFetchScheduleState(
            last_hour=GmailFetchWindowState(
                last_run_at=datetime(2026, 4, 2, 7, 5, 0),
                last_run_reason="auto",
                last_slot_key="2026-04-02T07:05:00+00:00",
            )
        )
    )

    state = store.load_state()

    assert state.last_hour.last_run_reason == "auto"


def test_due_gmail_fetch_windows_match_requested_schedule(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    schedule_state = GmailFetchScheduleState()

    due_at_0001 = service._due_gmail_fetch_windows(datetime(2026, 4, 2, 0, 1, 0).astimezone(), schedule_state)
    assert ("yesterday", "2026-04-01") in due_at_0001

    due_at_0600 = service._due_gmail_fetch_windows(datetime(2026, 4, 2, 6, 0, 0).astimezone(), schedule_state)
    assert ("today", "2026-04-02:1") in due_at_0600
    assert any(window == "last_hour" for window, _ in due_at_0600)

    due_at_0700 = service._due_gmail_fetch_windows(datetime(2026, 4, 2, 7, 0, 0).astimezone(), schedule_state)
    assert any(window == "last_hour" for window, _ in due_at_0700)

    due_at_0701 = service._due_gmail_fetch_windows(datetime(2026, 4, 2, 7, 1, 0).astimezone(), schedule_state)
    assert not any(window == "last_hour" for window, _ in due_at_0701)

    due_at_0705 = service._due_gmail_fetch_windows(datetime(2026, 4, 2, 7, 5, 0).astimezone(), schedule_state)
    assert any(window == "last_hour" for window, _ in due_at_0705)

    due_at_1801 = service._due_gmail_fetch_windows(datetime(2026, 4, 2, 18, 1, 0).astimezone(), schedule_state)
    assert ("today", "2026-04-02:3") in due_at_1801
    assert any(window == "last_hour" for window, _ in due_at_1801)


def test_due_gmail_fetch_windows_catch_up_missed_slot_in_local_timezone(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    now = datetime(2026, 4, 2, 18, 1, 0).astimezone()
    schedule_state = GmailFetchScheduleState(
        today=GmailFetchWindowState(last_slot_key="2026-04-02:2"),
        last_hour=GmailFetchWindowState(last_slot_key="2026-04-02T17:55:00+00:00"),
    )

    due_windows = service._due_gmail_fetch_windows(now, schedule_state)

    assert ("today", service._gmail_fetch_slot_key("today", now)) in due_windows
    assert ("last_hour", service._gmail_fetch_slot_key("last_hour", now)) in due_windows


@pytest.mark.asyncio
async def test_scheduled_hourly_batch_classification_runs_once_per_slot(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    calls: list[str | None] = []

    async def fake_runtime_execute_email_classifier_batch(payload, *, correlation_id=None):
        calls.append(payload.target_api_base_url)
        return {
            "ok": True,
            "batch_size": 0,
            "local_processed": 0,
            "local_classified": 0,
            "ai_total": 0,
            "ai_completed": 0,
            "ai_results": [],
        }

    service.runtime_execute_email_classifier_batch = fake_runtime_execute_email_classifier_batch  # type: ignore[method-assign]
    slot_time = datetime(2026, 4, 2, 7, 0, 0).astimezone()

    await service._run_due_hourly_batch_classification(slot_time)
    await service._run_due_hourly_batch_classification(slot_time.replace(minute=4))

    assert calls == ["http://127.0.0.1:9002"]
    assert service.state.gmail_hourly_batch_classification_slot_key == service._gmail_hourly_batch_slot_key(slot_time)
    assert service._gmail_hourly_batch_slot_key(slot_time.replace(minute=5)) is None


@pytest.mark.asyncio
async def test_scheduled_monthly_runtime_authorize_runs_once_per_slot(config, core_client_factory):
    core_app = build_core_app()
    service = NodeService(config, core_client=core_client_factory(core_app), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.node_id = "node-1"
    service.trust_material = TrustMaterial(
        node_id="node-1",
        node_type="email-node",
        paired_core_id="core-1",
        node_trust_token="trust-secret",
        operational_mqtt_identity="mqtt-user",
        operational_mqtt_token="mqtt-secret",
        operational_mqtt_host="127.0.0.1",
        operational_mqtt_port=1883,
    )
    slot_time = datetime(2026, 5, 1, 0, 1, 0).astimezone()

    await service._run_due_monthly_runtime_authorize(slot_time)
    await service._run_due_monthly_runtime_authorize(slot_time.replace(minute=4))

    await service.stop()

    assert len(core_app.state.service_resolve_requests) == 1
    assert len(core_app.state.service_authorize_requests) == 1
    assert core_app.state.service_resolve_requests[0]["type"] == "ai"
    assert core_app.state.service_authorize_requests[0]["type"] == "ai"
    assert core_app.state.service_authorize_requests[0]["service_id"] == "summary-service"
    assert core_app.state.service_authorize_requests[0]["provider"] == "openai"
    assert core_app.state.service_authorize_requests[0]["model_id"] == "gpt-5-mini"
    assert service.state.runtime_monthly_authorize_slot_key == "2026-05"
    assert service.state.runtime_monthly_authorize_last_run_at is not None
    assert service._runtime_monthly_authorize_slot_key(slot_time.replace(minute=5)) is None
