from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from email_node.shared_pipeline_core.decision import SharedDecisionResult


SharedPersistedTrustLevel = Literal["trusted", "partial"]


class SharedStructuredOutputRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "shared-structured-output.v1"
    flow_family: str
    persisted_at: datetime
    trust_level: SharedPersistedTrustLevel
    decision: str
    decision_reason: str
    confidence: float
    confidence_level: str
    extraction_source: str
    profile_id: str | None = None
    extracted_fields: dict[str, object] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
    message_metadata: dict[str, object] = Field(default_factory=dict)


class SharedOutputPersistenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: bool
    trust_level: SharedPersistedTrustLevel | None = None
    blocked_reason: str | None = None
    record_path: str | None = None
    diagnostics: list[str] = Field(default_factory=list)
    record: SharedStructuredOutputRecord | None = None


class SharedOutputPersistenceHandler:
    def __init__(self, *, flow_family: str, runtime_dir: Path | None = None) -> None:
        self.flow_family = str(flow_family)
        self.runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
        self.base_dir = self.runtime_dir / "flow_families" / self.flow_family / "outputs"
        self.trusted_dir = self.base_dir / "trusted"
        self.partial_dir = self.base_dir / "partial"

    def persist(self, *, decision: SharedDecisionResult, phase4) -> SharedOutputPersistenceResult:
        diagnostics = list(decision.diagnostics)
        if not decision.allow_persist_structured_result:
            blocked_reason = f"decision_blocked:{decision.decision_reason}"
            return SharedOutputPersistenceResult(
                persisted=False,
                blocked_reason=blocked_reason,
                diagnostics=diagnostics + [blocked_reason],
            )

        trust_level: SharedPersistedTrustLevel = "trusted" if decision.decision == "accept" else "partial"
        record = self.build_record(
            decision=decision,
            phase4=phase4,
            persisted_at=datetime.now(UTC),
            trust_level=trust_level,
        )
        output_dir = self.trusted_dir if trust_level == "trusted" else self.partial_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / self.record_filename(phase4)
        path.write_text(json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8")
        return SharedOutputPersistenceResult(
            persisted=True,
            trust_level=trust_level,
            record_path=str(path),
            diagnostics=diagnostics + [f"phase7_persisted:{trust_level}:{self._message_id(phase4)}"],
            record=record,
        )

    def build_record(
        self,
        *,
        decision: SharedDecisionResult,
        phase4,
        persisted_at: datetime,
        trust_level: SharedPersistedTrustLevel,
    ) -> SharedStructuredOutputRecord:
        return SharedStructuredOutputRecord(
            flow_family=self.flow_family,
            persisted_at=persisted_at,
            trust_level=trust_level,
            decision=decision.decision,
            decision_reason=decision.decision_reason,
            confidence=decision.confidence,
            confidence_level=decision.confidence_level,
            extraction_source=decision.extraction_source,
            profile_id=getattr(phase4, "profile_id", None),
            extracted_fields=self.serialize_extracted_fields(getattr(phase4, "extracted_fields", {}) or {}),
            diagnostics=list(decision.diagnostics),
            message_metadata=self.message_metadata(phase4),
        )

    def record_filename(self, phase4) -> str:
        return f"{self._message_id(phase4)}.json"

    @staticmethod
    def serialize_extracted_fields(extracted_fields: dict[str, object]) -> dict[str, object]:
        serialized: dict[str, object] = {}
        for key, value in extracted_fields.items():
            if hasattr(value, "model_dump"):
                serialized[key] = value.model_dump(mode="json")
            else:
                serialized[key] = value
        return serialized

    @staticmethod
    def message_metadata(phase4) -> dict[str, object]:
        return {
            "message_id": getattr(phase4, "message_id", None),
            "account_id": "primary",
            "subject": getattr(phase4, "subject", None),
            "sender_name": getattr(phase4, "sender_name", None),
            "sender_email": getattr(phase4, "sender_email", None),
            "sender_domain": getattr(phase4, "sender_domain", None),
            "received_at": getattr(phase4, "received_at", None),
        }

    @staticmethod
    def _message_id(phase4) -> str:
        return str(getattr(phase4, "message_id", "") or "unknown-message").strip() or "unknown-message"
