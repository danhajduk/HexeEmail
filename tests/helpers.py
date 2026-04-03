from __future__ import annotations

from fastapi import FastAPI, Header

from mqtt import MQTTManager


class FakeMQTTManager(MQTTManager):
    def __init__(self) -> None:
        super().__init__(heartbeat_seconds=0.01)
        self.connected_with = None

    def connect(self, trust_material) -> None:
        self.connected_with = trust_material
        self.status.state = "connected"

    def disconnect(self) -> None:
        self.status.state = "disconnected"


def build_core_app():
    app = FastAPI()
    app.state.sessions = {}
    app.state.capabilities = {}
    app.state.governance = {}
    app.state.governance_refresh_requests = []
    app.state.service_resolve_requests = []
    app.state.service_authorize_requests = []
    app.state.execution_direct_requests = []
    app.state.prompt_service_lifecycle_requests = []
    app.state.prompt_service_registration_requests = []
    app.state.usage_summary_requests = []

    @app.post("/api/system/nodes/onboarding/sessions")
    async def create_session(payload: dict):
        session_id = "sx_123"
        session = {
            "session_id": session_id,
            "approval_url": "http://core.test/approve/sx_123",
            "expires_at": "2026-03-20T12:00:00+00:00",
            "finalize": {"method": "GET", "path": f"/api/system/nodes/onboarding/sessions/{session_id}/finalize"},
        }
        app.state.sessions[session_id] = {"status": "pending", "request": payload}
        return session

    @app.get("/api/system/nodes/onboarding/sessions/{session_id}/finalize")
    async def finalize(session_id: str, node_nonce: str):
        session = app.state.sessions[session_id]
        if session["status"] == "approved":
            return {
                "onboarding_status": "approved",
                "activation": {
                    "node_id": "node-1",
                    "node_type": "email-node",
                    "paired_core_id": "core-1",
                    "node_trust_token": "trust-secret",
                    "operational_mqtt_identity": "mqtt-user",
                    "operational_mqtt_token": "mqtt-secret",
                    "operational_mqtt_host": "127.0.0.2",
                    "operational_mqtt_port": 1883,
                },
            }
        return {"onboarding_status": session["status"]}

    @app.get("/api/system/platform")
    async def get_platform_identity():
        return {
            "ok": True,
            "core_id": "a75d480287c33cab",
            "platform_name": "Hexe",
            "platform_short": "Hexe",
            "platform_domain": "hexe-ai.com",
            "core_name": "Hexe Core",
            "supervisor_name": "Supervisor",
            "nodes_name": "Nodes",
            "addons_name": "Addons",
            "docs_name": "Docs",
            "legacy_internal_namespace": "synthia",
            "legacy_compatibility_note": "compat",
            "public_hostname": "a75d480287c33cab.hexe-ai.com",
            "public_ui_hostname": "a75d480287c33cab.hexe-ai.com",
            "public_api_hostname": "a75d480287c33cab.hexe-ai.com",
        }

    @app.post("/api/system/nodes/capabilities/declaration")
    async def declare_capabilities(payload: dict, x_node_trust_token: str | None = Header(default=None)):
        assert x_node_trust_token == "trust-secret"
        manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
        node = manifest.get("node") if isinstance(manifest.get("node"), dict) else {}
        node_id = str(node.get("node_id") or "").strip()
        app.state.capabilities[node_id] = manifest
        return {
            "ok": True,
            "acceptance_status": "accepted",
            "node_id": node_id,
            "manifest_version": manifest.get("manifest_version"),
            "accepted_at": "2026-03-20T12:00:00+00:00",
            "declared_capabilities": manifest.get("declared_task_families") or [],
            "enabled_providers": manifest.get("enabled_providers") or [],
            "capability_profile_id": "profile-test",
            "governance_version": "phase2-test",
            "governance_issued_at": "2026-03-20T12:00:00+00:00",
        }

    @app.get("/api/system/nodes/governance/current")
    async def fetch_governance(node_id: str, x_node_trust_token: str | None = Header(default=None)):
        assert x_node_trust_token == "trust-secret"
        payload = {
            "routing_policy_constraints": {
                "allowed_providers": ["gmail"],
                "allowed_task_families": ["task.classification", "task.summarization", "task.tracking"],
                "allowed_models": {},
            },
            "provider_access": False,
        }
        app.state.governance[node_id] = payload
        return {
            "ok": True,
            "node_id": node_id,
            "capability_profile_id": "profile-test",
            "governance_version": "phase2-test",
            "issued_timestamp": "2026-03-20T12:00:00+00:00",
            "refresh_interval_s": 120,
            "governance_bundle": payload,
        }

    @app.post("/api/system/nodes/governance/refresh")
    async def refresh_governance(payload: dict, x_node_trust_token: str | None = Header(default=None)):
        assert x_node_trust_token == "trust-secret"
        app.state.governance_refresh_requests.append(payload)
        return {
            "ok": True,
            "node_id": payload.get("node_id"),
            "capability_profile_id": "profile-test",
            "governance_version": payload.get("current_governance_version") or "phase2-test",
            "updated": False,
            "refresh_interval_s": 120,
        }

    @app.post("/api/system/nodes/services/resolve")
    async def resolve_service(payload: dict, x_node_trust_token: str | None = Header(default=None)):
        assert x_node_trust_token == "trust-secret"
        app.state.service_resolve_requests.append(payload)
        return {
            "ok": True,
            "node_id": payload.get("node_id"),
            "task_family": payload.get("task_family"),
            "service_id": None,
            "provider": None,
            "model_id": None,
            "task_context": payload.get("task_context") or {},
            "selected_service_id": "summary-service",
            "candidates": [
                {
                    "service_id": "summary-service",
                    "provider_node_id": "node-provider-1",
                    "provider_api_base_url": "http://10.0.0.100:9002/api",
                    "service_type": "node-runtime",
                    "provider": payload.get("preferred_provider") or "openai",
                    "models_allowed": ["gpt-5-mini", "gpt-5.4-nano"],
                    "required_scopes": [f"service.execute:{payload.get('task_family')}"],
                    "auth_mode": "service_token",
                    "grant_id": "grant:provider-node:node",
                    "resolution_mode": "catalog_governance_budget",
                    "health_status": "healthy",
                    "declared_capacity": {},
                }
            ],
        }

    @app.post("/api/system/nodes/services/authorize")
    async def authorize_service(payload: dict, x_node_trust_token: str | None = Header(default=None)):
        assert x_node_trust_token == "trust-secret"
        app.state.service_authorize_requests.append(payload)
        return {
            "ok": True,
            "node_id": payload.get("node_id"),
            "task_family": payload.get("task_family"),
            "service_id": payload.get("service_id"),
            "provider": payload.get("provider"),
            "model_id": payload.get("model_id"),
            "authorized": True,
            "authorization_id": "auth-1",
            "grant_id": "grant:provider-node:node",
            "token": "service-token-1",
        }

    @app.post("/api/execution/direct")
    async def execute_direct(payload: dict, authorization: str | None = Header(default=None)):
        app.state.execution_direct_requests.append(payload)
        return {
            "task_id": payload.get("task_id"),
            "status": "completed",
            "output": {
                "label": "marketing",
                "confidence": 0.91,
                "rationale": "Promotional language and offer-style content.",
            },
            "metrics": {
                "total_tokens": 123,
            },
            "error_code": None,
            "error_message": None,
            "provider_used": payload.get("requested_provider") or "openai",
            "model_used": payload.get("requested_model") or "gpt-5-mini",
            "completed_at": "2026-04-02T12:34:56-07:00",
        }

    @app.post("/api/prompts/services/prompt.email.classifier/lifecycle")
    async def retire_prompt_service(payload: dict):
        app.state.prompt_service_lifecycle_requests.append(payload)
        return {
            "ok": True,
            "prompt_id": "prompt.email.classifier",
            "state": payload.get("state"),
            "reason": payload.get("reason"),
        }

    @app.post("/api/prompts/services")
    async def register_prompt_service(payload: dict):
        app.state.prompt_service_registration_requests.append(payload)
        return {
            "ok": True,
            "prompt_id": payload.get("prompt_id"),
            "service_id": payload.get("service_id"),
            "status": payload.get("status"),
            "version": payload.get("version"),
            "registered_at": "2026-04-02T22:05:00+00:00",
        }

    @app.post("/api/system/nodes/budgets/usage-summary")
    async def report_usage_summary(payload: dict, x_node_trust_token: str | None = Header(default=None)):
        assert x_node_trust_token == "trust-secret"
        app.state.usage_summary_requests.append(payload)
        return {
            "ok": True,
            "node_id": payload.get("node_id"),
            "report": payload,
        }

    return app
