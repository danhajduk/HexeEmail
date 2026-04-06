from __future__ import annotations

from email_node.shared_pipeline_core.validation import SharedValidationPolicy


VALIDATION_POLICY = SharedValidationPolicy(
    url_field_suffixes=("_url", "_action"),
    identifier_fields=("action_id", "document_id"),
    identifier_min_length=4,
    success_threshold=0.85,
    partial_threshold=0.5,
    required_field_confidence_weight=0.6,
    valid_field_confidence_weight=0.4,
)


def build_validation_policy() -> SharedValidationPolicy:
    return VALIDATION_POLICY
