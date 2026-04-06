from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserNotificationRequestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: bool
    title: str | None = None
    message: str | None = None
    severity: str | None = None
    dedupe_key: str | None = None
    source_metadata: dict[str, object] = Field(default_factory=dict)
    blocked_reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class UserNotificationHandler:
    def build_request(
        self,
        *,
        decision,
        action_routing,
        phase4,
    ) -> UserNotificationRequestResult:
        diagnostics = list(decision.diagnostics) + list(action_routing.diagnostics)
        if decision.decision not in {"accept", "review_needed"}:
            return UserNotificationRequestResult(
                queued=False,
                blocked_reason=f"decision:{decision.decision}",
                diagnostics=diagnostics + [f"user_notification:blocked:decision:{decision.decision}"],
            )
        if "user_notification" not in action_routing.action_intents:
            return UserNotificationRequestResult(
                queued=False,
                blocked_reason="missing_user_notification_intent",
                diagnostics=diagnostics + ["user_notification:blocked:missing_intent"],
            )

        extracted_fields = getattr(phase4, "extracted_fields", {}) or {}
        profile_id = str(getattr(phase4, "profile_id", "") or "")
        order_number = self._field_value(extracted_fields, "order_number")
        status = self._field_value(extracted_fields, "status")
        tracking_number = self._field_value(extracted_fields, "tracking_number")
        title, message = self._build_content(
            decision=decision.decision,
            profile_id=profile_id,
            order_number=order_number,
            status=status,
            tracking_number=tracking_number,
        )
        message_id = str(getattr(phase4, "message_id", "") or "unknown")
        dedupe_key = f"email-user-notification:{message_id}:{profile_id}:{order_number or tracking_number or 'na'}"
        return UserNotificationRequestResult(
            queued=True,
            title=title,
            message=message,
            severity="info",
            dedupe_key=dedupe_key,
            source_metadata={
                "message_id": message_id,
                "profile_id": profile_id,
                "sender_email": getattr(phase4, "sender_email", None),
                "subject": getattr(phase4, "subject", None),
            },
            diagnostics=diagnostics + [f"user_notification:queued:{dedupe_key}"],
        )

    @staticmethod
    def _build_content(
        *,
        decision: str,
        profile_id: str,
        order_number: str | None,
        status: str | None,
        tracking_number: str | None,
    ) -> tuple[str, str]:
        if decision == "review_needed":
            title = "Email review needed"
            message = f"Hexe Email needs review for {profile_id or 'this email flow result'}."
            return title, message
        if profile_id == "reservation_confirmation":
            title = "Reservation confirmed"
            message = f"Your order {order_number or 'reservation'} is confirmed."
            return title, message
        if profile_id in {"amazon_order_status_update", "generic_order_status_update"}:
            title = "Order update"
            status_text = status or "A tracking update is available."
            tracking_text = f" Tracking: {tracking_number}." if tracking_number else ""
            return title, f"{status_text}{tracking_text}".strip()
        title = "Order confirmed"
        message = f"Your order {order_number or 'details'} is ready."
        return title, message

    @staticmethod
    def _field_value(extracted_fields: dict[str, object], field_name: str) -> str | None:
        value = extracted_fields.get(field_name)
        if hasattr(value, "value"):
            value = getattr(value, "value")
        elif isinstance(value, dict):
            value = value.get("value")
        normalized = str(value or "").strip()
        return normalized or None
