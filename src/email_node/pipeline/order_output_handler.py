from __future__ import annotations
from datetime import datetime
from pathlib import Path

from pydantic import ConfigDict

from email_node.pipeline.order_decision_engine import OrderDecisionResult
from email_node.shared_pipeline_core.persistence import (
    SharedOutputPersistenceHandler,
    SharedOutputPersistenceResult,
    SharedPersistedTrustLevel,
    SharedStructuredOutputRecord,
)


PersistedTrustLevel = SharedPersistedTrustLevel


class OrderStructuredOutputRecord(SharedStructuredOutputRecord):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "order-structured-output.v1"
    flow_family: str = "order"


class OrderOutputPersistenceResult(SharedOutputPersistenceResult):
    record: OrderStructuredOutputRecord | None = None


class OrderOutputHandler(SharedOutputPersistenceHandler):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        super().__init__(flow_family="order", runtime_dir=runtime_dir)
        # Keep legacy output layout for ORDER while the shared framework stabilizes.
        self.base_dir = self.runtime_dir / "order_outputs"
        self.trusted_dir = self.base_dir / "trusted"
        self.partial_dir = self.base_dir / "partial"

    def persist(self, *, decision: OrderDecisionResult, phase4) -> OrderOutputPersistenceResult:
        result = super().persist(decision=decision, phase4=phase4)
        return OrderOutputPersistenceResult.model_validate(result.model_dump(mode="json"))

    def build_record(
        self,
        *,
        decision: OrderDecisionResult,
        phase4,
        persisted_at: datetime,
        trust_level: PersistedTrustLevel,
    ) -> OrderStructuredOutputRecord:
        diagnostics = list(decision.diagnostics)
        return OrderStructuredOutputRecord(
            persisted_at=persisted_at,
            trust_level=trust_level,
            decision=decision.decision,
            decision_reason=decision.decision_reason,
            confidence=decision.confidence,
            confidence_level=decision.confidence_level,
            extraction_source=decision.extraction_source,
            profile_id=getattr(phase4, "profile_id", None),
            extracted_fields=self.serialize_extracted_fields(getattr(phase4, "extracted_fields", {}) or {}),
            diagnostics=diagnostics,
            message_metadata=self.message_metadata(phase4),
        )
