from __future__ import annotations

from fastapi import APIRouter, HTTPException

from node_models.config import OperatorConfigInput
from service import NodeService


def build_node_router(node_service: NodeService) -> APIRouter:
    router = APIRouter()

    @router.get("/health/live")
    async def health_live():
        return {"live": True, "version": node_service.health_snapshot()["version"]}

    @router.get("/api/health")
    async def api_health():
        return {"status": "ok", **node_service.health_snapshot()}

    @router.get("/health/ready")
    async def health_ready():
        return node_service.health_snapshot()

    @router.get("/onboarding/status")
    async def onboarding_status():
        return node_service.onboarding_status()

    @router.get("/status")
    @router.get("/api/node/status")
    async def status():
        return await node_service.status()

    @router.get("/ui/bootstrap")
    @router.get("/api/node/bootstrap")
    async def ui_bootstrap():
        return await node_service.ui_bootstrap()

    @router.get("/ui/config")
    @router.get("/api/node/config")
    async def ui_config():
        return node_service.operator_config_response()

    @router.put("/ui/config")
    @router.put("/api/node/config")
    async def update_ui_config(payload: OperatorConfigInput):
        try:
            return await node_service.update_operator_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/ui/onboarding/start")
    @router.post("/api/onboarding/start")
    async def start_ui_onboarding():
        try:
            return await node_service.start_onboarding()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/ui/onboarding/restart")
    @router.post("/api/onboarding/restart")
    async def restart_ui_onboarding(payload: OperatorConfigInput):
        try:
            return await node_service.restart_setup(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
