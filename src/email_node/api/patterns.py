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

    return router
