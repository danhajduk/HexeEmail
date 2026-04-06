from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrackingMonitorRequestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: bool
    payload: dict[str, object] | None = None
    dedupe_key: str | None = None
    blocked_reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class TrackingMonitorHandler:
    def build_request(self, *, decision, action_routing, phase4) -> TrackingMonitorRequestResult:
        diagnostics = list(decision.diagnostics) + list(action_routing.diagnostics)
        if decision.decision != "accept":
            return TrackingMonitorRequestResult(
                queued=False,
                blocked_reason=f"decision:{decision.decision}",
                diagnostics=diagnostics + [f"tracking_monitor:blocked:decision:{decision.decision}"],
            )
        if "queue_tracking_monitor" not in action_routing.action_intents:
            return TrackingMonitorRequestResult(
                queued=False,
                blocked_reason="missing_queue_tracking_monitor_intent",
                diagnostics=diagnostics + ["tracking_monitor:blocked:missing_intent"],
            )

        extracted_fields = getattr(phase4, "extracted_fields", {}) or {}
        order_number = self._field_value(extracted_fields, "order_number")
        tracking_number = self._field_value(extracted_fields, "tracking_number")
        carrier = self._field_value(extracted_fields, "carrier")
        seller = self._field_value(extracted_fields, "seller") or getattr(phase4, "vendor_identity", None)
        current_status = self._field_value(extracted_fields, "status")
        if not tracking_number and not (carrier and order_number):
            return TrackingMonitorRequestResult(
                queued=False,
                blocked_reason="insufficient_tracking_identity",
                diagnostics=diagnostics + ["tracking_monitor:blocked:insufficient_identity"],
            )
        source_message_id = str(getattr(phase4, "message_id", "") or "unknown")
        dedupe_key = f"tracking-monitor:{tracking_number or f'{carrier}:{order_number}'}"
        return TrackingMonitorRequestResult(
            queued=True,
            payload={
                "order_number": order_number,
                "tracking_number": tracking_number,
                "carrier": carrier,
                "seller": seller,
                "current_status": current_status,
                "source_message_id": source_message_id,
            },
            dedupe_key=dedupe_key,
            diagnostics=diagnostics + [f"tracking_monitor:queued:{dedupe_key}"],
        )

    @staticmethod
    def _field_value(extracted_fields: dict[str, object], field_name: str) -> str | None:
        value = extracted_fields.get(field_name)
        if hasattr(value, "value"):
            value = getattr(value, "value")
        elif isinstance(value, dict):
            value = value.get("value")
        normalized = str(value or "").strip()
        return normalized or None
