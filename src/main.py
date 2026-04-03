from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from config import AppConfig
from logging_utils import correlation_id_middleware, setup_logging
from models import (
    CoreServiceAuthorizeRequestInput,
    CoreServiceResolveRequestInput,
    OperatorConfigInput,
    RefreshTriggerRequest,
    RuntimeDirectExecutionRequestInput,
    RuntimePromptExecutionRequestInput,
    ServiceRestartRequest,
    TaskCapabilitySelectionInput,
    TaskRoutingRequestInput,
)
from providers.gmail.models import GmailManualClassificationBatchInput, GmailOAuthConfig, GmailSemiAutoClassificationBatchInput, GmailTrainingLabel
from service import NodeService


def create_app(
    config: AppConfig | None = None,
    *,
    service: NodeService | None = None,
) -> FastAPI:
    setup_logging()
    app_config = config or AppConfig()
    node_service = service or NodeService(app_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = node_service
        await node_service.start()
        try:
            yield
        finally:
            await node_service.stop()

    app = FastAPI(title="Hexe Email Node", lifespan=lifespan)
    app.middleware("http")(correlation_id_middleware)

    @app.get("/health/live")
    async def health_live():
        return {"live": True, "version": node_service.health_snapshot()["version"]}

    @app.get("/api/health")
    async def api_health():
        return {"status": "ok", **node_service.health_snapshot()}

    @app.get("/health/ready")
    async def health_ready():
        return node_service.health_snapshot()

    @app.get("/onboarding/status")
    async def onboarding_status():
        return node_service.onboarding_status()

    @app.get("/status")
    @app.get("/api/node/status")
    async def status():
        return await node_service.status()

    @app.get("/ui/bootstrap")
    @app.get("/api/node/bootstrap")
    async def ui_bootstrap():
        return await node_service.ui_bootstrap()

    @app.get("/ui/config")
    @app.get("/api/node/config")
    async def ui_config():
        return node_service.operator_config_response()

    @app.put("/ui/config")
    @app.put("/api/node/config")
    async def update_ui_config(payload: OperatorConfigInput):
        try:
            return await node_service.update_operator_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ui/onboarding/start")
    @app.post("/api/onboarding/start")
    async def start_ui_onboarding():
        try:
            return await node_service.start_onboarding()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ui/onboarding/restart")
    @app.post("/api/onboarding/restart")
    async def restart_ui_onboarding(payload: OperatorConfigInput):
        try:
            return await node_service.restart_setup(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ui/capabilities/declare")
    @app.post("/api/capabilities/declare")
    async def declare_ui_capabilities():
        try:
            return await node_service.declare_selected_capabilities()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/capabilities/config")
    async def capability_config():
        return await node_service.capability_config_response()

    @app.post("/api/capabilities/config")
    async def update_capability_config(payload: TaskCapabilitySelectionInput):
        try:
            return await node_service.update_capability_config(
                OperatorConfigInput(selected_task_capabilities=payload.selected_task_capabilities)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/capabilities/diagnostics")
    async def capability_diagnostics():
        return await node_service.capability_diagnostics()

    @app.get("/api/capabilities/node/resolved")
    async def resolved_node_capabilities():
        return await node_service.resolved_node_capabilities()

    @app.post("/api/tasks/routing/preview")
    async def task_routing_preview(payload: TaskRoutingRequestInput):
        try:
            return await node_service.task_routing_preview(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/core/services/resolve")
    async def core_service_resolve(payload: CoreServiceResolveRequestInput, request: Request):
        try:
            return await node_service.core_service_resolve(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/core/services/authorize")
    async def core_service_authorize(payload: CoreServiceAuthorizeRequestInput, request: Request):
        try:
            return await node_service.core_service_authorize(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/runtime/execute-authorized-task")
    async def runtime_execute_authorized_task(payload: RuntimeDirectExecutionRequestInput, request: Request):
        try:
            return await node_service.runtime_execute_authorized_task(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=getattr(exc, "detail", str(exc))) from exc

    @app.post("/api/runtime/execute-email-classifier")
    async def runtime_execute_email_classifier(payload: RuntimePromptExecutionRequestInput, request: Request):
        try:
            return await node_service.runtime_execute_email_classifier(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/runtime/execute-email-classifier-batch")
    async def runtime_execute_email_classifier_batch(payload: RuntimePromptExecutionRequestInput, request: Request):
        try:
            return await node_service.runtime_execute_email_classifier_batch(
                payload,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/governance/status")
    async def governance_status():
        return await node_service.governance_status()

    @app.post("/api/governance/refresh")
    async def refresh_governance():
        try:
            return await node_service.refresh_governance()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/services/status")
    async def services_status():
        return await node_service.services_status()

    @app.post("/api/services/restart")
    async def restart_services(payload: ServiceRestartRequest):
        try:
            return await node_service.restart_service(payload.target)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/node/recover")
    async def recover_node():
        return await node_service.recover_node()

    @app.post("/api/capabilities/redeclare")
    async def redeclare_capabilities(payload: RefreshTriggerRequest):
        try:
            return await node_service.redeclare_capabilities(force=payload.force_refresh)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/capabilities/rebuild")
    async def rebuild_capabilities(payload: RefreshTriggerRequest):
        try:
            return await node_service.rebuild_capabilities(force=payload.force_refresh)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/providers/gmail/accounts/{account_id}/connect/start")
    async def start_gmail_connect(account_id: str, request: Request):
        try:
            return await node_service.start_gmail_connect(
                account_id,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/google/callback")
    async def gmail_oauth_callback(
        request: Request,
        state: str | None = None,
        code: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ):
        try:
            return await node_service.handle_gmail_oauth_callback(
                state=state,
                code=code,
                error=error,
                error_description=error_description,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/providers")
    async def providers():
        return await node_service.providers_overview()

    @app.get("/providers/gmail")
    async def gmail_provider():
        return await node_service.gmail_provider_status()

    @app.get("/api/gmail/status")
    async def gmail_status():
        return await node_service.gmail_status()

    @app.post("/api/gmail/fetch/{window}")
    async def gmail_fetch(window: str, request: Request, account_id: str = "primary"):
        try:
            return await node_service.gmail_fetch_messages(
                window,
                account_id=account_id,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/gmail/spamhaus/check")
    async def gmail_spamhaus_check(account_id: str = "primary"):
        try:
            return await node_service.gmail_check_spamhaus(account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/gmail/training")
    async def gmail_training(account_id: str = "primary"):
        try:
            return await node_service.gmail_training_status(account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/gmail/reputation")
    async def gmail_sender_reputation(account_id: str = "primary", limit: int = 20):
        try:
            return await node_service.gmail_sender_reputation_summary(account_id=account_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/gmail/reputation/detail")
    async def gmail_sender_reputation_detail(
        entity_type: str,
        sender_value: str,
        account_id: str = "primary",
        message_limit: int = 10,
    ):
        try:
            return await node_service.gmail_sender_reputation_detail(
                account_id=account_id,
                entity_type=entity_type,
                sender_value=sender_value,
                message_limit=message_limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/gmail/training/manual-batch")
    async def gmail_training_manual_batch(account_id: str = "primary", limit: int = 40):
        try:
            return await node_service.gmail_training_manual_batch(account_id=account_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/gmail/training/manual-classify")
    async def gmail_training_manual_classify(payload: GmailManualClassificationBatchInput, account_id: str = "primary"):
        try:
            return await node_service.gmail_training_save_manual_classifications(payload, account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/gmail/training/train-model")
    async def gmail_training_train_model(account_id: str = "primary", minimum_confidence: float | None = None):
        try:
            return await node_service.gmail_training_train_model(
                account_id=account_id,
                minimum_confidence=minimum_confidence,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/gmail/training/semi-auto-batch")
    async def gmail_training_semi_auto_batch(account_id: str = "primary", limit: int = 20):
        try:
            return await node_service.gmail_training_semi_auto_batch(account_id=account_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/gmail/training/classified-batch")
    async def gmail_training_classified_batch(label: GmailTrainingLabel, account_id: str = "primary", limit: int = 40):
        try:
            return await node_service.gmail_training_classified_batch(account_id=account_id, label=label, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/gmail/training/semi-auto-review")
    async def gmail_training_semi_auto_review(payload: GmailSemiAutoClassificationBatchInput, account_id: str = "primary"):
        try:
            return await node_service.gmail_training_save_semi_auto_review(payload, account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/providers/gmail/config")
    async def gmail_provider_config():
        try:
            return await node_service.gmail_provider_config()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/providers/gmail/config")
    async def update_gmail_provider_config(payload: GmailOAuthConfig):
        try:
            return await node_service.update_gmail_provider_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/providers/gmail/accounts")
    async def gmail_accounts():
        return await node_service.gmail_accounts_status()

    @app.get("/providers/gmail/accounts/{account_id}")
    async def gmail_account(account_id: str):
        return await node_service.gmail_account_status(account_id)

    @app.post("/providers/gmail/validate-config")
    async def gmail_validate_config():
        return await node_service.gmail_config_validation()

    return app
