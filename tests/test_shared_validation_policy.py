from __future__ import annotations

from email_node.shared_pipeline_core.validation import SharedValidationPolicy
from providers.gmail.models import GmailPhase4ExtractedField


def _is_missing_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def test_shared_validation_policy_marks_missing_required_and_invalid_fields():
    policy = SharedValidationPolicy()
    fields = {
        "order_number": GmailPhase4ExtractedField(field_name="order_number", value="12"),
        "order_action_url": GmailPhase4ExtractedField(field_name="order_action_url", value="not-a-url"),
    }

    validated, diagnostics = policy.validate_fields(
        fields,
        required_fields=["order_number", "status"],
        is_missing_value=_is_missing_value,
    )

    assert "missing_required:status" in diagnostics
    assert "invalid_field:order_number" in diagnostics
    assert "invalid_field:order_action_url" in diagnostics
    assert validated["status"].is_required is True
    assert validated["order_number"].is_valid is False
    assert validated["order_action_url"].is_valid is False


def test_shared_validation_policy_scores_partial_confidence_with_missing_required():
    policy = SharedValidationPolicy()
    fields = {
        "order_number": GmailPhase4ExtractedField(field_name="order_number", value="112-0381957-4204214", is_valid=True),
        "status": GmailPhase4ExtractedField(field_name="status", value=None, is_valid=False),
    }

    confidence, level, diagnostics, status = policy.score_extraction_confidence(
        fields,
        required_fields=["order_number", "status"],
        is_missing_value=_is_missing_value,
    )

    assert confidence == 0.5
    assert level == "medium"
    assert status == "partial"
    assert "confidence_downgrade:missing_required_fields" in diagnostics
