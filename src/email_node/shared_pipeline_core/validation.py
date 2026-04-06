from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from providers.gmail.models import GmailPhase4ExtractedField


@dataclass(frozen=True, slots=True)
class SharedValidationPolicy:
    url_field_suffixes: tuple[str, ...] = ("_url",)
    identifier_fields: tuple[str, ...] = ("order_number", "tracking_number")
    identifier_min_length: int = 6
    success_threshold: float = 0.85
    partial_threshold: float = 0.5
    required_field_confidence_weight: float = 0.6
    valid_field_confidence_weight: float = 0.4

    @classmethod
    def from_mapping(cls, payload: dict[str, object]) -> SharedValidationPolicy:
        allowed_keys = {
            "url_field_suffixes",
            "identifier_fields",
            "identifier_min_length",
            "success_threshold",
            "partial_threshold",
            "required_field_confidence_weight",
            "valid_field_confidence_weight",
        }
        normalized: dict[str, object] = {}
        for key, value in payload.items():
            if key not in allowed_keys:
                continue
            if key in {"url_field_suffixes", "identifier_fields"} and isinstance(value, (list, tuple)):
                normalized[key] = tuple(str(item) for item in value)
            elif key == "identifier_min_length" and isinstance(value, (int, float)):
                normalized[key] = int(value)
            elif key in {"success_threshold", "partial_threshold", "required_field_confidence_weight", "valid_field_confidence_weight"} and isinstance(value, (int, float)):
                normalized[key] = float(value)
        return cls(**normalized)

    def validate_fields(
        self,
        extracted_fields: dict[str, GmailPhase4ExtractedField],
        *,
        required_fields: object,
        is_missing_value,
    ) -> tuple[dict[str, GmailPhase4ExtractedField], list[str]]:
        required = [str(item) for item in required_fields or []]
        diagnostics: list[str] = []
        updated = dict(extracted_fields)
        for field_name in required:
            field = updated.get(field_name)
            if field is None or is_missing_value(field.value):
                diagnostics.append(f"missing_required:{field_name}")
                updated[field_name] = GmailPhase4ExtractedField(
                    field_name=field_name,
                    value=None,
                    is_valid=False,
                    is_required=True,
                    diagnostics=["required_field_missing"],
                )
                continue
            updated[field_name] = field.model_copy(update={"is_required": True})
        for field_name, field in list(updated.items()):
            value = field.value
            field_diags = list(field.diagnostics)
            is_valid = field.is_valid
            if self._is_url_field(field_name) and isinstance(value, str):
                parsed = urlparse(value)
                if not parsed.scheme or not parsed.netloc:
                    is_valid = False
                    field_diags.append("invalid_url_shape")
                    diagnostics.append(f"invalid_field:{field_name}")
            if field_name in self.identifier_fields and isinstance(value, str):
                if len(re.sub(r"[^A-Z0-9-]", "", value.upper())) < self.identifier_min_length:
                    is_valid = False
                    field_diags.append("value_too_short")
                    diagnostics.append(f"invalid_field:{field_name}")
            updated[field_name] = field.model_copy(update={"is_valid": is_valid, "diagnostics": field_diags})
        return updated, diagnostics

    def score_extraction_confidence(
        self,
        extracted_fields: dict[str, GmailPhase4ExtractedField],
        *,
        required_fields: object,
        is_missing_value,
    ) -> tuple[float, str, list[str], str]:
        required = [str(item) for item in required_fields or []]
        diagnostics: list[str] = []
        present_required = sum(
            1 for name in required if name in extracted_fields and not is_missing_value(extracted_fields[name].value)
        )
        total_required = len(required)
        valid_fields = sum(1 for field in extracted_fields.values() if field.is_valid and not is_missing_value(field.value))
        total_fields = max(1, len(extracted_fields))
        confidence = 0.0
        if total_required:
            confidence += self.required_field_confidence_weight * (present_required / total_required)
        confidence += self.valid_field_confidence_weight * (valid_fields / total_fields)
        confidence = round(min(1.0, confidence), 2)
        if total_required and present_required < total_required:
            diagnostics.append("confidence_downgrade:missing_required_fields")
        if valid_fields < total_fields:
            diagnostics.append("confidence_downgrade:invalid_optional_fields")
        if confidence >= self.success_threshold:
            return confidence, "high", diagnostics, "success"
        if confidence >= self.partial_threshold:
            return confidence, "medium", diagnostics, "partial"
        return confidence, "low", diagnostics, "partial"

    def _is_url_field(self, field_name: str) -> bool:
        return any(field_name.endswith(suffix) for suffix in self.url_field_suffixes)
