from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from email_node.pipeline.order_action_gate import OrderActionAuthorizationResult
from email_node.pipeline.order_decision_engine import OrderDecisionResult


OrderActionIntent = Literal[
    "store_order_record",
    "update_order_record",
    "attach_tracking_reference",
    "user_notification",
    "queue_tracking_monitor",
    "mark_for_manual_review",
]


class OrderActionRoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_intents: list[OrderActionIntent] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class OrderActionRouter:
    def route(
        self,
        *,
        decision: OrderDecisionResult,
        authorization: OrderActionAuthorizationResult,
        phase4,
    ) -> OrderActionRoutingResult:
        diagnostics = list(decision.diagnostics) + list(authorization.diagnostics)
        if not authorization.actions_allowed:
            return OrderActionRoutingResult(action_intents=[], diagnostics=diagnostics + ["action_router:blocked"])

        profile_id = str(getattr(phase4, "profile_id", "") or "")
        extracted_fields = getattr(phase4, "extracted_fields", {}) or {}
        tracking_number = self._field_value(extracted_fields, "tracking_number")
        carrier = self._field_value(extracted_fields, "carrier")
        order_number = self._field_value(extracted_fields, "order_number")

        intents: list[OrderActionIntent] = []
        if profile_id in {"reservation_confirmation", "amazon_order_confirmation", "generic_order_confirmation"}:
            intents.append("store_order_record")
        if profile_id in {"amazon_order_status_update", "generic_order_status_update"}:
            intents.append("update_order_record")
        if tracking_number and (carrier or order_number):
            intents.extend(["attach_tracking_reference", "queue_tracking_monitor"])
        if decision.decision == "accept":
            intents.append("user_notification")
        if any("important_inconsistency" in item for item in diagnostics):
            intents.append("mark_for_manual_review")

        deduped = list(dict.fromkeys(intents))
        return OrderActionRoutingResult(action_intents=deduped, diagnostics=diagnostics + [f"action_router:intents:{','.join(deduped) or 'none'}"])

    @staticmethod
    def _field_value(extracted_fields: dict[str, object], field_name: str) -> str | None:
        value = extracted_fields.get(field_name)
        if hasattr(value, "value"):
            value = getattr(value, "value")
        elif isinstance(value, dict):
            value = value.get("value")
        normalized = str(value or "").strip()
        return normalized or None
