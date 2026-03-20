from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from config import AppConfig


class FinalizeRoute(BaseModel):
    method: str = "GET"
    path: str | None = None


class OnboardingSessionRequest(BaseModel):
    node_name: str
    node_type: str
    node_software_version: str
    protocol_version: str
    node_nonce: str
    hostname: str | None = None


class OnboardingSessionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    approval_url: str
    expires_at: str | None = None
    node_name: str | None = None
    node_type: str | None = None
    node_software_version: str | None = None
    finalize: FinalizeRoute | dict[str, Any] | None = None


class ActivationPayload(BaseModel):
    node_id: str
    node_type: str
    paired_core_id: str
    node_trust_token: str
    operational_mqtt_identity: str
    operational_mqtt_token: str
    operational_mqtt_host: str
    operational_mqtt_port: int
    issued_at: str | None = None
    source_session_id: str | None = None
    trust_status: str = "trusted"


class FinalizeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    onboarding_status: str = Field(default="pending")
    activation: ActivationPayload | None = None
    approval_url: str | None = None
    session_id: str | None = None
    expires_at: str | None = None
    error_code: str | None = None
    message: str | None = None


class TrustStatusResponse(BaseModel):
    ok: bool = True
    node_id: str
    trust_status: str
    supported: bool
    support_state: str | None = None
    message: str | None = None


class CoreApiClient:
    def __init__(self, config: AppConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=str(config.core_base_url).rstrip("/"),
            timeout=10.0,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_onboarding_session(self, request: OnboardingSessionRequest, correlation_id: str) -> OnboardingSessionResponse:
        payload = request.model_dump(mode="json")
        headers = {"X-Correlation-Id": correlation_id}

        for attempt in range(2):
            response = await self._client.post("/api/system/nodes/onboarding/sessions", json=payload, headers=headers)
            if response.status_code in (200, 201):
                return OnboardingSessionResponse.model_validate(response.json())

            if response.status_code == 409:
                body = response.json()
                session_payload = body.get("session") if isinstance(body, dict) else None
                if isinstance(session_payload, dict):
                    return OnboardingSessionResponse.model_validate(session_payload)
                if isinstance(body, dict):
                    return OnboardingSessionResponse.model_validate(body)

            if response.status_code >= 500 and attempt == 0:
                await asyncio.sleep(0.5)
                continue

            response.raise_for_status()

        raise RuntimeError("failed to create onboarding session")

    async def finalize_onboarding(self, session_id: str, node_nonce: str, correlation_id: str) -> FinalizeResponse:
        response = await self._client.get(
            f"/api/system/nodes/onboarding/sessions/{session_id}/finalize",
            params={"node_nonce": node_nonce},
            headers={"X-Correlation-Id": correlation_id},
        )
        response.raise_for_status()
        return FinalizeResponse.model_validate(response.json())

    async def get_trust_status(self, node_id: str, trust_token: str, correlation_id: str) -> TrustStatusResponse:
        response = await self._client.get(
            f"/api/system/nodes/trust-status/{node_id}",
            headers={
                "X-Correlation-Id": correlation_id,
                "X-Node-Trust-Token": trust_token,
            },
        )
        response.raise_for_status()
        return TrustStatusResponse.model_validate(response.json())
