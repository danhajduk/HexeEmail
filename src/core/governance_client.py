from __future__ import annotations

from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field


class GovernanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    present: bool
    synced_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    last_sync_result: str = "ok"
    payload: dict[str, object] = Field(default_factory=dict)


class GovernanceClient:
    FETCH_PATH_TEMPLATE = "/api/system/nodes/{node_id}/governance"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def fetch(
        self,
        base_url: str,
        node_id: str,
        *,
        correlation_id: str | None = None,
    ) -> GovernanceSnapshot:
        headers = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        response = await self._client.get(
            f"{base_url.rstrip('/')}{self.FETCH_PATH_TEMPLATE.format(node_id=node_id)}",
            headers=headers,
        )
        payload: dict[str, object] = {}
        if not response.is_error:
            try:
                body = response.json()
                if isinstance(body, dict):
                    payload = body
            except ValueError:
                payload = {}
        return GovernanceSnapshot(
            node_id=node_id,
            present=not response.is_error,
            last_sync_result="ok" if not response.is_error else f"http_{response.status_code}",
            payload=payload,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
