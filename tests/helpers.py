from __future__ import annotations

from fastapi import FastAPI

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

    @app.post("/api/system/nodes/{node_id}/capabilities")
    async def declare_capabilities(node_id: str, payload: dict):
        app.state.capabilities[node_id] = payload
        return {"ok": True}

    @app.get("/api/system/nodes/{node_id}/governance")
    async def fetch_governance(node_id: str):
        payload = {
            "node_id": node_id,
            "policy_version": "phase2-test",
            "provider_access": False,
        }
        app.state.governance[node_id] = payload
        return payload

    return app
