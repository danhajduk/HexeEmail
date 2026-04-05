from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


ProbationTemplateStatus = Literal["probation", "active", "rejected", "archived"]


class ProbationTemplateState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    profile_id: str
    template_version: str
    status: ProbationTemplateStatus = "probation"
    created_at: datetime
    updated_at: datetime
    sample_count: int = 1
    success_count: int = 0
    failure_count: int = 0
    hard_failure_count: int = 0
    required_field_success_rate: float = 0.0
    high_requires_success_rate: float = 0.0
    last_evaluated_at: datetime | None = None
    promotion_eligible: bool = False
    promotion_reason: str | None = None

    @field_validator("template_id", "profile_id", "template_version")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("sample_count", "success_count", "failure_count", "hard_failure_count")
    @classmethod
    def validate_non_negative_counts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be non-negative")
        return value

    @field_validator("required_field_success_rate", "high_requires_success_rate")
    @classmethod
    def validate_rate_range(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("must be between 0 and 1")
        return value
