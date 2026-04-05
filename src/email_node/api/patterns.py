from __future__ import annotations

from fastapi import APIRouter, HTTPException

from email_node.patterns import PatternGenerationRequest
from service import NodeService


def build_pattern_router(node_service: NodeService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/patterns/generate")
    async def generate_pattern(payload: PatternGenerationRequest):
        try:
            return await node_service.generate_pattern_template(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/patterns/probation")
    async def list_probation_templates():
        return node_service.list_probation_templates()

    @router.get("/api/patterns/probation/{template_id}")
    async def get_probation_template(template_id: str):
        return node_service.get_probation_template(template_id)

    @router.get("/api/patterns/probation/{template_id}/evaluations")
    async def get_probation_evaluations(template_id: str):
        return node_service.list_probation_evaluations(template_id)

    return router
