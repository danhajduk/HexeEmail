from __future__ import annotations

from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: str
    node: dict[str, str]
    declared_task_families: list[str] = Field(default_factory=list)
    supported_providers: list[str] = Field(default_factory=list)
    enabled_providers: list[str] = Field(default_factory=list)
    node_features: dict[str, bool] = Field(default_factory=dict)
    environment_hints: dict[str, str] = Field(default_factory=dict)


class CapabilityDeclarationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    detail: str | None = None
    manifest: CapabilityManifest


class CapabilityManifestBuilder:
    def build(
        self,
        *,
        node_id: str,
        node_type: str,
        node_name: str,
        node_software_version: str,
        declared_task_families: list[str],
        supported_providers: list[str],
        enabled_providers: list[str],
    ) -> CapabilityManifest:
        return CapabilityManifest(
            manifest_version="1.0",
            node={
                "node_id": node_id,
                "node_type": node_type,
                "node_name": node_name,
                "node_software_version": node_software_version,
            },
            declared_task_families=sorted({family.strip() for family in declared_task_families if family.strip()}),
            supported_providers=sorted(supported_providers),
            enabled_providers=sorted(enabled_providers),
            node_features={
                "telemetry": True,
                "governance_refresh": True,
                "lifecycle_events": True,
                "provider_failover": False,
            },
            environment_hints={
                "deployment_target": "node",
                "acceleration": "none",
                "network_tier": "lan",
                "region": "local",
            },
        )


class CapabilityClient:
    DECLARE_PATH = "/api/system/nodes/capabilities/declaration"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def declare(
        self,
        base_url: str,
        manifest: CapabilityManifest,
        *,
        trust_token: str,
        correlation_id: str | None = None,
    ) -> CapabilityDeclarationResult:
        headers = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        headers["X-Node-Trust-Token"] = trust_token
        response = await self._client.post(
            f"{base_url.rstrip('/')}{self.DECLARE_PATH}",
            json={"manifest": manifest.model_dump(mode="json")},
            headers=headers,
        )
        if response.is_error:
            detail = None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    raw_detail = payload.get("detail")
                    if isinstance(raw_detail, str):
                        detail = raw_detail
                    elif isinstance(raw_detail, dict):
                        detail = raw_detail.get("message") if isinstance(raw_detail.get("message"), str) else None
            except ValueError:
                detail = None
            return CapabilityDeclarationResult(accepted=False, detail=detail, manifest=manifest)
        return CapabilityDeclarationResult(accepted=True, manifest=manifest)

    async def aclose(self) -> None:
        await self._client.aclose()
