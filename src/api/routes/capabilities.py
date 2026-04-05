from __future__ import annotations

from fastapi import APIRouter, HTTPException

from node_models.config import OperatorConfigInput, TaskCapabilitySelectionInput
from node_models.runtime import RefreshTriggerRequest
from service import NodeService


def build_capabilities_router(node_service: NodeService) -> APIRouter:
    router = APIRouter()

    @router.post("/ui/capabilities/declare")
    @router.post("/api/capabilities/declare")
    async def declare_ui_capabilities():
        try:
            return await node_service.declare_selected_capabilities()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/capabilities/config")
    async def capability_config():
        return await node_service.capability_config_response()

    @router.post("/api/capabilities/config")
    async def update_capability_config(payload: TaskCapabilitySelectionInput):
        try:
            return await node_service.update_capability_config(
                OperatorConfigInput(selected_task_capabilities=payload.selected_task_capabilities)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/capabilities/diagnostics")
    async def capability_diagnostics():
        return await node_service.capability_diagnostics()

    @router.get("/api/capabilities/node/resolved")
    async def resolved_node_capabilities():
        return await node_service.resolved_node_capabilities()

    @router.post("/api/capabilities/redeclare")
    async def redeclare_capabilities(payload: RefreshTriggerRequest):
        try:
            return await node_service.redeclare_capabilities(force=payload.force_refresh)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/capabilities/rebuild")
    async def rebuild_capabilities(payload: RefreshTriggerRequest):
        try:
            return await node_service.rebuild_capabilities(force=payload.force_refresh)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
