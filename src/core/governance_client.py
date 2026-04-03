from __future__ import annotations

from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field

from logging_utils import get_logger


LOGGER = get_logger(__name__)


class GovernanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    present: bool
    synced_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    last_sync_result: str = "ok"
    governance_version: str | None = None
    refresh_interval_s: int | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class GovernanceClient:
    CURRENT_PATH = "/api/system/nodes/governance/current"
    REFRESH_PATH = "/api/system/nodes/governance/refresh"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def fetch(
        self,
        base_url: str,
        node_id: str,
        *,
        trust_token: str,
        current_governance_version: str | None = None,
        correlation_id: str | None = None,
    ) -> GovernanceSnapshot:
        headers = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        headers["X-Node-Trust-Token"] = trust_token
        payload: dict[str, object] = {}
        governance_version: str | None = None
        refresh_interval_s: int | None = None

        if current_governance_version:
            LOGGER.info(
                "Refreshing governance with Core",
                extra={
                    "event_data": {
                        "base_url": base_url,
                        "node_id": node_id,
                        "current_governance_version": current_governance_version,
                    }
                },
            )
            refresh_response = await self._client.post(
                f"{base_url.rstrip('/')}{self.REFRESH_PATH}",
                json={
                    "node_id": node_id,
                    "current_governance_version": current_governance_version,
                },
                headers=headers,
            )
            if refresh_response.is_error:
                LOGGER.warning(
                    "Governance refresh failed",
                    extra={"event_data": {"status_code": refresh_response.status_code, "node_id": node_id}},
                )
                return GovernanceSnapshot(
                    node_id=node_id,
                    present=False,
                    last_sync_result=f"http_{refresh_response.status_code}",
                )
            try:
                refresh_body = refresh_response.json()
            except ValueError:
                refresh_body = {}
            if isinstance(refresh_body, dict):
                governance_version = (
                    str(refresh_body.get("governance_version")).strip() if refresh_body.get("governance_version") else None
                )
                refresh_interval_s = (
                    int(refresh_body.get("refresh_interval_s"))
                    if refresh_body.get("refresh_interval_s") is not None
                    else None
                )
                bundle = refresh_body.get("governance_bundle")
                if isinstance(bundle, dict):
                    payload = bundle
                    LOGGER.info(
                        "Governance refresh returned bundle",
                        extra={
                            "event_data": {
                                "node_id": node_id,
                                "governance_version": governance_version,
                                "refresh_interval_s": refresh_interval_s,
                            }
                        },
                    )
                    return GovernanceSnapshot(
                        node_id=node_id,
                        present=True,
                        last_sync_result="ok",
                        governance_version=governance_version,
                        refresh_interval_s=refresh_interval_s,
                        payload=payload,
                    )

        LOGGER.info(
            "Fetching current governance from Core",
            extra={"event_data": {"base_url": base_url, "node_id": node_id}},
        )
        response = await self._client.get(
            f"{base_url.rstrip('/')}{self.CURRENT_PATH}",
            params={"node_id": node_id},
            headers=headers,
        )
        if not response.is_error:
            try:
                body = response.json()
                if isinstance(body, dict):
                    governance_version = str(body.get("governance_version")).strip() if body.get("governance_version") else governance_version
                    refresh_interval_s = (
                        int(body.get("refresh_interval_s")) if body.get("refresh_interval_s") is not None else refresh_interval_s
                    )
                    bundle = body.get("governance_bundle")
                    payload = bundle if isinstance(bundle, dict) else {}
            except ValueError:
                payload = {}
        if response.is_error:
            LOGGER.warning(
                "Governance fetch failed",
                extra={"event_data": {"status_code": response.status_code, "node_id": node_id}},
            )
        else:
            LOGGER.info(
                "Governance fetch completed",
                extra={
                    "event_data": {
                        "status_code": response.status_code,
                        "node_id": node_id,
                        "governance_version": governance_version,
                    }
                },
            )
        return GovernanceSnapshot(
            node_id=node_id,
            present=not response.is_error,
            last_sync_result="ok" if not response.is_error else f"http_{response.status_code}",
            governance_version=governance_version,
            refresh_interval_s=refresh_interval_s,
            payload=payload,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
