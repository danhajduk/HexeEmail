from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from node_models.runtime import (
    CoreServiceAuthorizeRequestInput,
    CoreServiceResolveRequestInput,
    RuntimePromptExecutionRequestInput,
    RuntimeDirectExecutionRequestInput,
    RuntimeTaskSettingsInput,
    RuntimePromptSyncRequestInput,
    TaskRoutingRequestInput,
)
from service import NodeService


def build_runtime_router(node_service: NodeService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/tasks/routing/preview")
    async def task_routing_preview(payload: TaskRoutingRequestInput):
        try:
            return await node_service.task_routing_preview(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/core/services/resolve")
    async def core_service_resolve(payload: CoreServiceResolveRequestInput, request: Request):
        try:
            return await node_service.core_service_resolve(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/core/services/authorize")
    async def core_service_authorize(payload: CoreServiceAuthorizeRequestInput, request: Request):
        try:
            return await node_service.core_service_authorize(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/runtime/execute-authorized-task")
    async def runtime_execute_authorized_task(payload: RuntimeDirectExecutionRequestInput, request: Request):
        try:
            return await node_service.runtime_execute_authorized_task(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=getattr(exc, "detail", str(exc))) from exc

    @router.post("/api/runtime/prompts/sync")
    async def runtime_sync_prompts(payload: RuntimePromptSyncRequestInput, request: Request):
        try:
            return await node_service.runtime_sync_prompts(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=getattr(exc, "detail", str(exc))) from exc

    @router.post("/api/runtime/settings")
    async def runtime_update_settings(payload: RuntimeTaskSettingsInput):
        try:
            return await node_service.update_runtime_task_settings(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/runtime/execute-email-classifier")
    async def runtime_execute_email_classifier(payload: RuntimePromptExecutionRequestInput, request: Request):
        try:
            return await node_service.runtime_execute_email_classifier(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/runtime/execute-email-classifier-batch")
    async def runtime_execute_email_classifier_batch(payload: RuntimePromptExecutionRequestInput, request: Request):
        try:
            return await node_service.runtime_execute_email_classifier_batch(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/runtime/execute-latest-email-action-decision")
    async def runtime_execute_latest_email_action_decision(payload: RuntimePromptExecutionRequestInput, request: Request):
        try:
            return await node_service.runtime_execute_latest_email_action_decision(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
