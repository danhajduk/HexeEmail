from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from providers.gmail.models import (
    GmailManualClassificationBatchInput,
    GmailOAuthConfig,
    GmailSenderReputationManualRatingInput,
    GmailSemiAutoClassificationBatchInput,
    GmailTrainingLabel,
)
from service import NodeService


def build_providers_gmail_router(node_service: NodeService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/providers/gmail/accounts/{account_id}/connect/start")
    @router.post("/providers/gmail/accounts/{account_id}/connect/start")
    async def start_gmail_connect(account_id: str, request: Request):
        try:
            return await node_service.start_gmail_connect(
                account_id,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/providers/gmail/oauth/callback")
    @router.get("/google/gmail/callback")
    @router.get("/google/callback")
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

    @router.get("/api/providers")
    @router.get("/providers")
    async def providers():
        return await node_service.providers_overview()

    @router.get("/api/providers/gmail")
    @router.get("/providers/gmail")
    async def gmail_provider():
        return await node_service.gmail_provider_status()

    @router.get("/api/gmail/status")
    async def gmail_status():
        return await node_service.gmail_status()

    @router.post("/api/gmail/fetch/{window}")
    async def gmail_fetch(window: str, request: Request, account_id: str = "primary"):
        try:
            return await node_service.gmail_fetch_messages(
                window,
                account_id=account_id,
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/spamhaus/check")
    async def gmail_spamhaus_check(account_id: str = "primary"):
        try:
            return await node_service.gmail_check_spamhaus(account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/reputation/refresh")
    async def gmail_sender_reputation_refresh(account_id: str = "primary"):
        try:
            return await node_service.gmail_refresh_sender_reputation(account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/gmail/training")
    async def gmail_training(account_id: str = "primary"):
        try:
            return await node_service.gmail_training_status(account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/gmail/reputation")
    async def gmail_sender_reputation(account_id: str = "primary", limit: int = 20):
        try:
            return await node_service.gmail_sender_reputation_summary(account_id=account_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/gmail/reputation/detail")
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

    @router.post("/api/gmail/reputation/manual-rating")
    async def gmail_sender_reputation_manual_rating(
        payload: GmailSenderReputationManualRatingInput,
        account_id: str = "primary",
    ):
        try:
            return await node_service.gmail_save_sender_reputation_manual_rating(
                account_id=account_id,
                entity_type=payload.entity_type,
                sender_value=payload.sender_value,
                manual_rating=payload.manual_rating,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/training/manual-batch")
    async def gmail_training_manual_batch(account_id: str = "primary", limit: int = 40):
        try:
            return await node_service.gmail_training_manual_batch(account_id=account_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/training/manual-classify")
    async def gmail_training_manual_classify(payload: GmailManualClassificationBatchInput, account_id: str = "primary"):
        try:
            return await node_service.gmail_training_save_manual_classifications(payload, account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/training/train-model")
    async def gmail_training_train_model(account_id: str = "primary", minimum_confidence: float | None = None):
        try:
            return await node_service.gmail_training_train_model(
                account_id=account_id,
                minimum_confidence=minimum_confidence,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/training/semi-auto-batch")
    async def gmail_training_semi_auto_batch(account_id: str = "primary", limit: int = 20):
        try:
            return await node_service.gmail_training_semi_auto_batch(account_id=account_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/training/classified-batch")
    async def gmail_training_classified_batch(label: GmailTrainingLabel, account_id: str = "primary", limit: int = 40):
        try:
            return await node_service.gmail_training_classified_batch(account_id=account_id, label=label, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/gmail/training/semi-auto-review")
    async def gmail_training_semi_auto_review(payload: GmailSemiAutoClassificationBatchInput, account_id: str = "primary"):
        try:
            return await node_service.gmail_training_save_semi_auto_review(payload, account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/providers/gmail/config")
    @router.get("/providers/gmail/config")
    async def gmail_provider_config():
        try:
            return await node_service.gmail_provider_config()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/api/providers/gmail/config")
    @router.put("/providers/gmail/config")
    async def update_gmail_provider_config(payload: GmailOAuthConfig):
        try:
            return await node_service.update_gmail_provider_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/providers/gmail/accounts")
    @router.get("/providers/gmail/accounts")
    async def gmail_accounts():
        return await node_service.gmail_accounts_status()

    @router.get("/api/providers/gmail/accounts/{account_id}")
    @router.get("/providers/gmail/accounts/{account_id}")
    async def gmail_account(account_id: str):
        return await node_service.gmail_account_status(account_id)

    @router.post("/api/providers/gmail/validate-config")
    @router.post("/providers/gmail/validate-config")
    async def gmail_validate_config():
        return await node_service.gmail_config_validation()

    return router
