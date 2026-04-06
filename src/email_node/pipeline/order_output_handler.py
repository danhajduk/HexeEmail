from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from email_node.pipeline.order_decision_engine import OrderDecisionResult


PersistedTrustLevel = Literal["trusted", "partial"]


class OrderStructuredOutputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "order-structured-output.v1"
    persisted_at: datetime
    trust_level: PersistedTrustLevel
    decision: str
    decision_reason: str
    confidence: float
    confidence_level: str
    extraction_source: str
    profile_id: str | None = None
    extracted_fields: dict[str, object] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
    message_metadata: dict[str, object] = Field(default_factory=dict)


class OrderOutputPersistenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: bool
    trust_level: PersistedTrustLevel | None = None
    blocked_reason: str | None = None
    record_path: str | None = None
    diagnostics: list[str] = Field(default_factory=list)
    record: OrderStructuredOutputRecord | None = None


class OrderOutputHandler:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
        self.base_dir = self.runtime_dir / "order_outputs"
        self.trusted_dir = self.base_dir / "trusted"
        self.partial_dir = self.base_dir / "partial"

    def persist(self, *, decision: OrderDecisionResult, phase4) -> OrderOutputPersistenceResult:
        diagnostics = list(decision.diagnostics)
        if not decision.allow_persist_structured_result:
            blocked_reason = f"decision_blocked:{decision.decision_reason}"
            return OrderOutputPersistenceResult(
                persisted=False,
                blocked_reason=blocked_reason,
                diagnostics=diagnostics + [blocked_reason],
            )

        trust_level: PersistedTrustLevel = "trusted" if decision.decision == "accept" else "partial"
        persisted_at = datetime.now(UTC)
        record = OrderStructuredOutputRecord(
            persisted_at=persisted_at,
            trust_level=trust_level,
            decision=decision.decision,
            decision_reason=decision.decision_reason,
            confidence=decision.confidence,
            confidence_level=decision.confidence_level,
            extraction_source=decision.extraction_source,
            profile_id=getattr(phase4, "profile_id", None),
            extracted_fields=self._serialize_extracted_fields(getattr(phase4, "extracted_fields", {}) or {}),
            diagnostics=diagnostics,
            message_metadata=self._message_metadata(phase4),
        )
        output_dir = self.trusted_dir if trust_level == "trusted" else self.partial_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        message_id = str(getattr(phase4, "message_id", "") or "unknown-message").strip() or "unknown-message"
        path = output_dir / f"{message_id}.json"
        path.write_text(json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8")
        return OrderOutputPersistenceResult(
            persisted=True,
            trust_level=trust_level,
            record_path=str(path),
            diagnostics=diagnostics + [f"phase7_persisted:{trust_level}:{message_id}"],
            record=record,
        )

    @staticmethod
    def _serialize_extracted_fields(extracted_fields: dict[str, object]) -> dict[str, object]:
        serialized: dict[str, object] = {}
        for key, value in extracted_fields.items():
            if hasattr(value, "model_dump"):
                serialized[key] = value.model_dump(mode="json")
            else:
                serialized[key] = value
        return serialized

    @staticmethod
    def _message_metadata(phase4) -> dict[str, object]:
        return {
            "message_id": getattr(phase4, "message_id", None),
            "account_id": "primary",
            "subject": getattr(phase4, "subject", None),
            "sender_name": getattr(phase4, "sender_name", None),
            "sender_email": getattr(phase4, "sender_email", None),
            "sender_domain": getattr(phase4, "sender_domain", None),
            "received_at": getattr(phase4, "received_at", None),
        }
