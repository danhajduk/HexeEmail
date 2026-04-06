from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_record_id: str
    profile_id: str
    order_number: str | None = None
    status: str | None = None
    seller: str | None = None
    carrier: str | None = None
    item_titles: list[str] = Field(default_factory=list)
    total: str | None = None
    currency: str | None = None
    delivery_date: str | None = None
    delivery_window: str | None = None
    tracking_number: str | None = None
    source_message_id: str
    source_account_id: str
    extraction_source: str
    confidence: float
    created_at: datetime
    updated_at: datetime


class OrderRecordWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    written: bool
    operation: Literal["created", "updated", "skipped"]
    blocked_reason: str | None = None
    order_record_id: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class OrderRecordService:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
        self.records_dir = self.runtime_dir / "order_records"
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def write_from_order_result(
        self,
        *,
        decision,
        phase4,
        action_routing,
    ) -> OrderRecordWriteResult:
        if decision.decision != "accept":
            return OrderRecordWriteResult(
                written=False,
                operation="skipped",
                blocked_reason=f"decision:{decision.decision}",
                diagnostics=list(decision.diagnostics) + [f"order_record:skipped:decision:{decision.decision}"],
            )
        if "store_order_record" not in action_routing.action_intents and "update_order_record" not in action_routing.action_intents:
            return OrderRecordWriteResult(
                written=False,
                operation="skipped",
                blocked_reason="no_record_intent",
                diagnostics=list(action_routing.diagnostics) + ["order_record:skipped:no_record_intent"],
            )

        extracted_fields = getattr(phase4, "extracted_fields", {}) or {}
        order_number = self._field_value(extracted_fields, "order_number")
        tracking_number = self._field_value(extracted_fields, "tracking_number")
        existing = self._find_existing_record(order_number=order_number, tracking_number=tracking_number, source_message_id=getattr(phase4, "message_id", None))
        now = datetime.now(UTC)
        created_at = existing.created_at if existing is not None else now
        order_record_id = existing.order_record_id if existing is not None else self._build_record_id(order_number=order_number, tracking_number=tracking_number, message_id=str(getattr(phase4, "message_id", "") or "unknown"))
        record = OrderRecord(
            order_record_id=order_record_id,
            profile_id=str(getattr(phase4, "profile_id", "") or "unknown"),
            order_number=order_number,
            status=self._field_value(extracted_fields, "status"),
            seller=self._field_value(extracted_fields, "seller") or getattr(phase4, "vendor_identity", None),
            carrier=self._field_value(extracted_fields, "carrier"),
            item_titles=self._item_titles(extracted_fields),
            total=self._field_value(extracted_fields, "total"),
            currency=self._currency(extracted_fields),
            delivery_date=self._field_value(extracted_fields, "delivery_date"),
            delivery_window=self._field_value(extracted_fields, "delivery_window"),
            tracking_number=tracking_number,
            source_message_id=str(getattr(phase4, "message_id", "") or "unknown"),
            source_account_id="primary",
            extraction_source=decision.extraction_source,
            confidence=decision.confidence,
            created_at=created_at,
            updated_at=now,
        )
        path = self.records_dir / f"{record.order_record_id}.json"
        path.write_text(json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8")
        return OrderRecordWriteResult(
            written=True,
            operation="updated" if existing is not None else "created",
            order_record_id=record.order_record_id,
            diagnostics=list(action_routing.diagnostics) + [f"order_record:written:{record.order_record_id}"],
        )

    def _find_existing_record(
        self,
        *,
        order_number: str | None,
        tracking_number: str | None,
        source_message_id: str | None,
    ) -> OrderRecord | None:
        for path in sorted(self.records_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = OrderRecord.model_validate(payload)
            if order_number and record.order_number == order_number:
                return record
            if tracking_number and record.tracking_number == tracking_number:
                return record
            if source_message_id and record.source_message_id == source_message_id:
                return record
        return None

    @staticmethod
    def _build_record_id(*, order_number: str | None, tracking_number: str | None, message_id: str) -> str:
        if order_number:
            return f"order:{order_number}"
        if tracking_number:
            return f"tracking:{tracking_number}"
        return f"message:{message_id}"

    @staticmethod
    def _field_value(extracted_fields: dict[str, object], field_name: str) -> str | None:
        value = extracted_fields.get(field_name)
        if hasattr(value, "value"):
            value = getattr(value, "value")
        elif isinstance(value, dict):
            value = value.get("value")
        normalized = str(value or "").strip()
        return normalized or None

    def _item_titles(self, extracted_fields: dict[str, object]) -> list[str]:
        item_name = self._field_value(extracted_fields, "item_name")
        if item_name:
            return [item_name]
        return []

    def _currency(self, extracted_fields: dict[str, object]) -> str | None:
        total = self._field_value(extracted_fields, "total")
        if not total:
            return None
        upper = total.upper()
        for token in ("USD", "EUR", "GBP"):
            if token in upper:
                return token
        return None
