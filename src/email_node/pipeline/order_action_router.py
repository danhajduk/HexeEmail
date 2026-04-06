from __future__ import annotations

from email_node.pipeline.order_action_gate import OrderActionAuthorizationResult
from email_node.pipeline.order_decision_engine import OrderDecisionResult
from email_node.shared_pipeline_core.actions import (
    SharedActionIntent,
    SharedActionRouter,
    SharedActionRoutingResult,
)


OrderActionIntent = SharedActionIntent


class OrderActionRoutingResult(SharedActionRoutingResult):
    pass


class OrderActionRouter(SharedActionRouter):
    def route(
        self,
        *,
        decision: OrderDecisionResult,
        authorization: OrderActionAuthorizationResult,
        phase4,
    ) -> OrderActionRoutingResult:
        result = super().route(decision=decision, authorization=authorization, phase4=phase4)
        return OrderActionRoutingResult.model_validate(result.model_dump(mode="json"))

    def resolve_action_intents(
        self,
        *,
        decision: OrderDecisionResult,
        authorization: OrderActionAuthorizationResult,
        phase4,
    ) -> list[OrderActionIntent]:
        diagnostics = list(decision.diagnostics) + list(authorization.diagnostics)
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
        return intents

    @staticmethod
    def _field_value(extracted_fields: dict[str, object], field_name: str) -> str | None:
        value = extracted_fields.get(field_name)
        if hasattr(value, "value"):
            value = getattr(value, "value")
        elif isinstance(value, dict):
            value = value.get("value")
        normalized = str(value or "").strip()
        return normalized or None
