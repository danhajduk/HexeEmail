from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatternGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    profile_id: str
    template_version: str = "v1"
    vendor_identity: str
    expected_label: str
    from_name: str
    from_email: str
    subject: str
    received_at: str
    body_text: str
    body_html: str = ""
    links_json: list[dict[str, object]] = Field(default_factory=list)

    @field_validator("template_id", "profile_id", "vendor_identity", "from_name", "from_email", "subject", "received_at", mode="before")
    @classmethod
    def validate_required_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("template_version", mode="before")
    @classmethod
    def normalize_template_version(cls, value: object) -> str:
        if value is None:
            return "v1"
        if not isinstance(value, str):
            raise ValueError("must be a string")
        stripped = value.strip()
        return stripped or "v1"

    @field_validator("expected_label", mode="before")
    @classmethod
    def validate_expected_label(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        normalized = value.strip().upper()
        if normalized not in {"ORDER", "SHIPMENT"}:
            raise ValueError("expected_label must be ORDER or SHIPMENT")
        return normalized

    @field_validator("body_text", mode="before")
    @classmethod
    def validate_body_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("body_text must not be empty")
        return stripped

    @field_validator("body_html", mode="before")
    @classmethod
    def normalize_body_html(cls, value: object) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return value
