from __future__ import annotations

from fastapi import FastAPI

from email_node.mqtt import MQTTManager


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

    return app
