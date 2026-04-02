from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


class FinalizeRoute(BaseModel):
    method: str = "GET"
    path: str | None = None


class PlatformIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    core_id: str


class OnboardingSessionRequest(BaseModel):
    node_name: str
    node_type: str
    node_software_version: str
    protocol_version: str
    node_nonce: str
    hostname: str | None = None
    ui_endpoint: str | None = None
    api_base_url: str | None = None


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
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 10.0) -> None:
        self.transport = transport
        self.timeout = timeout

    async def aclose(self) -> None:
        return None

    def _client(self, base_url: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=self.timeout,
            transport=self.transport,
        )

    async def create_onboarding_session(
        self,
        base_url: str,
        request: OnboardingSessionRequest,
        correlation_id: str,
    ) -> OnboardingSessionResponse:
        payload = request.model_dump(mode="json")
        headers = {"X-Correlation-Id": correlation_id}

        async with self._client(base_url) as client:
            for attempt in range(2):
                response = await client.post("/api/system/nodes/onboarding/sessions", json=payload, headers=headers)
                if response.status_code in (200, 201):
                    return self._parse_onboarding_session_response(response.json())

                if response.status_code == 409:
                    reusable_session = self._extract_reusable_session(response.json())
                    if reusable_session is not None:
                        return reusable_session

                if response.status_code >= 500 and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue

                response.raise_for_status()

        raise RuntimeError("failed to create onboarding session")

    def _parse_onboarding_session_response(self, body: Any) -> OnboardingSessionResponse:
        if isinstance(body, dict):
            session_payload = body.get("session")
            if isinstance(session_payload, dict):
                return OnboardingSessionResponse.model_validate(session_payload)
        return OnboardingSessionResponse.model_validate(body)

    def _extract_reusable_session(self, body: Any) -> OnboardingSessionResponse | None:
        if not isinstance(body, dict):
            return None

        direct_session = body.get("session")
        if isinstance(direct_session, dict):
            return OnboardingSessionResponse.model_validate(direct_session)

        if "session_id" in body and "approval_url" in body:
            return OnboardingSessionResponse.model_validate(body)

        detail = body.get("detail")
        if not isinstance(detail, dict):
            return None

        for key in ("session", "existing_session", "active_session"):
            candidate = detail.get(key)
            if isinstance(candidate, dict):
                return OnboardingSessionResponse.model_validate(candidate)

        if "session_id" in detail and "approval_url" in detail:
            return OnboardingSessionResponse.model_validate(detail)

        return None

    async def finalize_onboarding(
        self,
        base_url: str,
        session_id: str,
        node_nonce: str,
        correlation_id: str,
    ) -> FinalizeResponse:
        async with self._client(base_url) as client:
            response = await client.get(
                f"/api/system/nodes/onboarding/sessions/{session_id}/finalize",
                params={"node_nonce": node_nonce},
                headers={"X-Correlation-Id": correlation_id},
            )
            response.raise_for_status()
            return FinalizeResponse.model_validate(response.json())

    async def get_platform_identity(self, base_url: str) -> PlatformIdentityResponse:
        async with self._client(base_url) as client:
            response = await client.get("/api/system/platform")
            response.raise_for_status()
            return PlatformIdentityResponse.model_validate(response.json())

    async def get_trust_status(
        self,
        base_url: str,
        node_id: str,
        trust_token: str,
        correlation_id: str,
    ) -> TrustStatusResponse:
        async with self._client(base_url) as client:
            response = await client.get(
                f"/api/system/nodes/trust-status/{node_id}",
                headers={
                    "X-Correlation-Id": correlation_id,
                    "X-Node-Trust-Token": trust_token,
                },
            )
            response.raise_for_status()
            return TrustStatusResponse.model_validate(response.json())
