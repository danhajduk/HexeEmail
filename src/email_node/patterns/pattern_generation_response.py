from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SUPPORTED_TRANSFORMS = Literal[
    "trim",
    "collapse_spaces",
    "normalize_currency",
    "normalize_order_number",
    "normalize_phone_number",
    "normalize_url",
]


class _BaseExtractRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    transforms: list[SUPPORTED_TRANSFORMS] = Field(default_factory=list)


class RegexExtractRule(_BaseExtractRule):
    method: Literal["regex"]
    pattern: str


class LineContainsExtractRule(_BaseExtractRule):
    method: Literal["line_contains"]
    value: str


class LineAfterExtractRule(_BaseExtractRule):
    method: Literal["line_after"]
    marker: str


class BetweenMarkersExtractRule(_BaseExtractRule):
    method: Literal["between_markers"]
    start_marker: str
    end_marker: str


class AllMatchesExtractRule(_BaseExtractRule):
    method: Literal["all_matches"]
    pattern: str


class FirstMatchExtractRule(_BaseExtractRule):
    method: Literal["first_match"]
    pattern: str


class LinkByLabelExtractRule(_BaseExtractRule):
    method: Literal["link_by_label"]
    label: str


class LinkByTypeExtractRule(_BaseExtractRule):
    method: Literal["link_by_type"]
    link_type: str


ExtractRule = Annotated[
    RegexExtractRule
    | LineContainsExtractRule
    | LineAfterExtractRule
    | BetweenMarkersExtractRule
    | AllMatchesExtractRule
    | FirstMatchExtractRule
    | LinkByLabelExtractRule
    | LinkByTypeExtractRule,
    Field(discriminator="method"),
]


class PatternGenerationMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_identity: str

    @field_validator("vendor_identity")
    @classmethod
    def validate_vendor_identity(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("vendor_identity must not be empty")
        return stripped


class PatternGenerationConfidenceRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high_requires: list[str] = Field(default_factory=list)


class PatternGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["order-phase4-template.v1"]
    template_id: str
    profile_id: str
    template_version: Literal["v1"]
    enabled: bool
    match: PatternGenerationMatch
    extract: dict[str, ExtractRule] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    confidence_rules: PatternGenerationConfidenceRules
    post_process: dict[str, object] = Field(default_factory=dict)

    @field_validator("template_id", "profile_id")
    @classmethod
    def validate_non_empty_ids(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped
