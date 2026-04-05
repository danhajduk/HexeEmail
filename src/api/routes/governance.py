from __future__ import annotations

from fastapi import APIRouter, HTTPException

from node_models.runtime import ServiceRestartRequest
from service import NodeService


def build_governance_router(node_service: NodeService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/governance/status")
    async def governance_status():
        return await node_service.governance_status()

    @router.post("/api/governance/refresh")
    async def refresh_governance():
        try:
            return await node_service.refresh_governance()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/services/status")
    async def services_status():
        return await node_service.services_status()

    @router.post("/api/services/restart")
    async def restart_services(payload: ServiceRestartRequest):
        try:
            return await node_service.restart_service(payload.target)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/node/recover")
    async def recover_node():
        return await node_service.recover_node()

    return router
