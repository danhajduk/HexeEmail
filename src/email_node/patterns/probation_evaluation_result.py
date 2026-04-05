from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProbationEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    message_id: str
    profile_id: str
    matched: bool
    extraction_succeeded: bool
    required_fields_present: bool
    missing_required_fields: list[str] = Field(default_factory=list)
    high_requires_present: bool
    missing_high_requires: list[str] = Field(default_factory=list)
    extracted_fields: dict[str, object] = Field(default_factory=dict)
    confidence_score: float = 0.0
    hard_failure: bool = False
    failure_reason: str | None = None
    evaluated_at: datetime

    @field_validator("template_id", "message_id", "profile_id")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence_range(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence_score must be between 0 and 1")
        return value
