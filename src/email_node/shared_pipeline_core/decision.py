from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SharedDecision = Literal["accept", "probation", "reject"]
SharedExtractionSource = Literal["active", "probation"]


class SharedDecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: SharedDecision
    decision_reason: str
    allow_persist_structured_result: bool
    allow_downstream_actions: bool
    requires_manual_review: bool
    confidence: float = 0.0
    confidence_level: Literal["high", "medium", "low"] = "low"
    extraction_source: SharedExtractionSource = "active"
    profile_id: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SharedDecisionPolicy:
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.60


class SharedDecisionEngine:
    def __init__(self, *, policy: SharedDecisionPolicy | None = None) -> None:
        self.policy = policy or SharedDecisionPolicy()

    def decide(self, phase4) -> SharedDecisionResult:
        extraction_source = self._determine_extraction_source(phase4)
        confidence = round(float(getattr(phase4, "extraction_confidence", 0.0) or 0.0), 2)
        confidence_level = self._normalize_confidence_level(
            getattr(phase4, "extraction_confidence_level", None),
            confidence=confidence,
        )
        diagnostics = self._collect_diagnostics(phase4)
        profile_id = getattr(phase4, "profile_id", None)
        extraction_status = str(getattr(phase4, "extraction_status", "failed") or "failed")
        has_structured_result = bool(getattr(phase4, "extracted_fields", {}))
        hard_validation_failure = self._has_hard_validation_failure(phase4, diagnostics)

        if hard_validation_failure:
            return SharedDecisionResult(
                decision="reject",
                decision_reason="hard_validation_failure",
                allow_persist_structured_result=False,
                allow_downstream_actions=False,
                requires_manual_review=True,
                confidence=confidence,
                confidence_level=confidence_level,
                extraction_source=extraction_source,
                profile_id=profile_id,
                diagnostics=diagnostics + ["decision:reject", "decision_reason:hard_validation_failure"],
            )

        if extraction_source == "probation":
            return SharedDecisionResult(
                decision="probation",
                decision_reason="probation_template_result",
                allow_persist_structured_result=has_structured_result,
                allow_downstream_actions=False,
                requires_manual_review=True,
                confidence=confidence,
                confidence_level=confidence_level,
                extraction_source=extraction_source,
                profile_id=profile_id,
                diagnostics=diagnostics + ["decision:probation", "decision_reason:probation_template_result"],
            )

        if extraction_status in {"failed", "unresolved"} or not has_structured_result:
            return SharedDecisionResult(
                decision="reject",
                decision_reason="no_structured_extraction",
                allow_persist_structured_result=False,
                allow_downstream_actions=False,
                requires_manual_review=True,
                confidence=confidence,
                confidence_level=confidence_level,
                extraction_source=extraction_source,
                profile_id=profile_id,
                diagnostics=diagnostics + ["decision:reject", "decision_reason:no_structured_extraction"],
            )

        if confidence >= self.policy.high_confidence_threshold:
            return SharedDecisionResult(
                decision="accept",
                decision_reason="active_high_confidence",
                allow_persist_structured_result=True,
                allow_downstream_actions=True,
                requires_manual_review=False,
                confidence=confidence,
                confidence_level=confidence_level,
                extraction_source=extraction_source,
                profile_id=profile_id,
                diagnostics=diagnostics + ["decision:accept", "decision_reason:active_high_confidence"],
            )

        if confidence >= self.policy.medium_confidence_threshold:
            return SharedDecisionResult(
                decision="probation",
                decision_reason="active_medium_confidence",
                allow_persist_structured_result=True,
                allow_downstream_actions=False,
                requires_manual_review=True,
                confidence=confidence,
                confidence_level=confidence_level,
                extraction_source=extraction_source,
                profile_id=profile_id,
                diagnostics=diagnostics + ["decision:probation", "decision_reason:active_medium_confidence"],
            )

        return SharedDecisionResult(
            decision="reject",
            decision_reason="active_low_confidence",
            allow_persist_structured_result=False,
            allow_downstream_actions=False,
            requires_manual_review=True,
            confidence=confidence,
            confidence_level=confidence_level,
            extraction_source=extraction_source,
            profile_id=profile_id,
            diagnostics=diagnostics + ["decision:reject", "decision_reason:active_low_confidence"],
        )

    @staticmethod
    def _determine_extraction_source(phase4) -> SharedExtractionSource:
        template_diagnostics = [str(item) for item in getattr(phase4, "template_diagnostics", []) or []]
        if any(item.startswith("probation_template:applied:") for item in template_diagnostics):
            return "probation"
        return "active"

    @staticmethod
    def _collect_diagnostics(phase4) -> list[str]:
        diagnostics: list[str] = []
        diagnostics.extend(str(item) for item in getattr(phase4, "template_diagnostics", []) or [])
        diagnostics.extend(str(item) for item in getattr(phase4, "field_diagnostics", []) or [])
        return diagnostics

    @staticmethod
    def _has_hard_validation_failure(phase4, diagnostics: list[str]) -> bool:
        if any(item.startswith("invalid_field:") for item in diagnostics):
            return True
        stage_statuses = dict(getattr(phase4, "stage_statuses", {}) or {})
        if stage_statuses.get("field_validation") == "failed":
            return True
        return str(getattr(phase4, "extraction_status", "failed") or "failed") == "failed"

    def _normalize_confidence_level(self, value: object, *, confidence: float) -> Literal["high", "medium", "low"]:
        if value in {"high", "medium", "low"}:
            return value
        if confidence >= self.policy.high_confidence_threshold:
            return "high"
        if confidence >= self.policy.medium_confidence_threshold:
            return "medium"
        return "low"
