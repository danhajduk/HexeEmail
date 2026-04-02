from __future__ import annotations

from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_type: str
    node_name: str
    node_software_version: str
    declared_task_families: list[str] = Field(default_factory=list)
    supported_providers: list[str] = Field(default_factory=list)
    enabled_providers: list[str] = Field(default_factory=list)
    node_features: list[str] = Field(default_factory=list)
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
            node_id=node_id,
            node_type=node_type,
            node_name=node_name,
            node_software_version=node_software_version,
            declared_task_families=sorted({family.strip() for family in declared_task_families if family.strip()}),
            supported_providers=sorted(supported_providers),
            enabled_providers=sorted(enabled_providers),
            node_features=[
                "provider-oauth",
                "provider-health",
                "provider-status-api",
            ],
            environment_hints={
                "runtime": "email-node",
                "classification_mode": "classification-first",
            },
        )


class CapabilityClient:
    DECLARE_PATH_TEMPLATE = "/api/system/nodes/{node_id}/capabilities"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def declare(
        self,
        base_url: str,
        manifest: CapabilityManifest,
        *,
        correlation_id: str | None = None,
    ) -> CapabilityDeclarationResult:
        headers = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        response = await self._client.post(
            f"{base_url.rstrip('/')}{self.DECLARE_PATH_TEMPLATE.format(node_id=manifest.node_id)}",
            json=manifest.model_dump(mode="json"),
            headers=headers,
        )
        if response.is_error:
            detail = None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = payload.get("detail") if isinstance(payload.get("detail"), str) else None
            except ValueError:
                detail = None
            return CapabilityDeclarationResult(accepted=False, detail=detail, manifest=manifest)
        return CapabilityDeclarationResult(accepted=True, manifest=manifest)

    async def aclose(self) -> None:
        await self._client.aclose()
