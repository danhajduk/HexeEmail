from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from providers.gmail.models import (
    GmailActionItemNoteInput,
    GmailActionItemReclassifyInput,
    GmailActionItemRuleFeedbackInput,
    GmailActionItemSnoozeInput,
    GmailActionItemStateUpdateInput,
    GmailManualClassificationBatchInput,
    GmailOAuthConfig,
    GmailRulesInput,
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

    @router.get("/api/gmail/rules")
    async def gmail_rules(account_id: str = "primary"):
        try:
            return await node_service.gmail_rules(account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/api/gmail/rules")
    async def update_gmail_rules(payload: GmailRulesInput, account_id: str = "primary"):
        try:
            return await node_service.update_gmail_rules(payload, account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @router.post("/api/shipments/{account_id}/{record_id}/live-tracking/enable")
    async def enable_shipment_live_tracking(account_id: str, record_id: str):
        try:
            return await node_service.enable_shipment_live_tracking(account_id=account_id, record_id=record_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/shipments/{account_id}/{record_id}/live-tracking/refresh")
    async def refresh_shipment_live_tracking(account_id: str, record_id: str):
        try:
            return await node_service.refresh_shipment_live_tracking(account_id=account_id, record_id=record_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/tracking/track123/couriers")
    async def track123_couriers():
        try:
            return await node_service.list_track123_couriers()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/shipments/backfill-from-outputs")
    async def backfill_shipments_from_outputs(account_id: str = "primary"):
        try:
            return node_service.backfill_tracked_orders_from_shipment_outputs(account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/actions")
    @router.get("/api/gmail/action-items")
    async def gmail_action_items(
        account_id: str = "primary",
        states: str | None = None,
        profile: str | None = None,
        sender: str | None = None,
        review_needed: bool | None = None,
        high_priority: bool | None = None,
        due_before: str | None = None,
        grouped: bool | None = None,
        limit: int = 100,
    ):
        try:
            return await node_service.gmail_action_items(
                account_id=account_id,
                states=states,
                profile=profile,
                sender=sender,
                review_needed=review_needed,
                high_priority=high_priority,
                due_before=due_before,
                grouped=grouped,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/actions/{item_id}")
    @router.get("/api/gmail/action-items/{item_id}")
    async def gmail_action_item_detail(item_id: str, account_id: str = "primary"):
        try:
            return await node_service.gmail_action_item_detail(account_id=account_id, item_id=item_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.patch("/api/actions/{item_id}/state")
    @router.patch("/api/gmail/action-items/{item_id}/state")
    async def update_gmail_action_item_state(
        item_id: str,
        payload: GmailActionItemStateUpdateInput,
        account_id: str = "primary",
    ):
        try:
            return await node_service.gmail_update_action_item_state(
                account_id=account_id,
                item_id=item_id,
                state=payload.state,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/api/actions/{item_id}/snooze")
    @router.patch("/api/gmail/action-items/{item_id}/snooze")
    async def snooze_gmail_action_item(
        item_id: str,
        payload: GmailActionItemSnoozeInput,
        account_id: str = "primary",
    ):
        try:
            return await node_service.gmail_snooze_action_item(
                account_id=account_id,
                item_id=item_id,
                snoozed_until=payload.snoozed_until,
                reminder_at=payload.reminder_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/api/actions/{item_id}/note")
    @router.patch("/api/gmail/action-items/{item_id}/note")
    async def update_gmail_action_item_note(
        item_id: str,
        payload: GmailActionItemNoteInput,
        account_id: str = "primary",
    ):
        try:
            return await node_service.gmail_update_action_item_note(
                account_id=account_id,
                item_id=item_id,
                operator_note=payload.operator_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/api/actions/{item_id}/classification")
    @router.patch("/api/gmail/action-items/{item_id}/classification")
    async def reclassify_gmail_action_item(
        item_id: str,
        payload: GmailActionItemReclassifyInput,
        account_id: str = "primary",
    ):
        try:
            return await node_service.gmail_reclassify_action_item(
                account_id=account_id,
                item_id=item_id,
                label=payload.label,
                confidence=payload.confidence,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/actions/{item_id}/rule-feedback")
    @router.post("/api/gmail/action-items/{item_id}/rule-feedback")
    async def apply_gmail_action_item_rule_feedback(
        item_id: str,
        payload: GmailActionItemRuleFeedbackInput,
        account_id: str = "primary",
    ):
        try:
            return await node_service.gmail_apply_action_item_rule_feedback(
                account_id=account_id,
                item_id=item_id,
                scope=payload.scope,
                label=payload.label,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/actions/{item_id}/notify")
    @router.post("/api/gmail/action-items/{item_id}/notify")
    async def notify_gmail_action_item(item_id: str, account_id: str = "primary"):
        try:
            return await node_service.gmail_send_action_item_notification(account_id=account_id, item_id=item_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/actions/{item_id}/regenerate-ai-decision")
    @router.post("/api/gmail/action-items/{item_id}/regenerate-ai-decision")
    async def regenerate_gmail_action_item_ai_decision(item_id: str, account_id: str = "primary"):
        try:
            return await node_service.gmail_regenerate_action_item_ai_decision(account_id=account_id, item_id=item_id)
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
