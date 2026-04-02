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

    return app
