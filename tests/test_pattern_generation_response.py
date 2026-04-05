from __future__ import annotations

import pytest
from pydantic import ValidationError

from email_node.patterns.pattern_generation_response import PatternGenerationResponse


def test_pattern_generation_response_accepts_valid_template():
    payload = PatternGenerationResponse.model_validate(
        {
            "schema_version": "order-phase4-template.v1",
            "template_id": "amazon_order_confirmation.v1",
            "profile_id": "amazon_order_confirmation",
            "template_version": "v1",
            "enabled": True,
            "match": {"vendor_identity": "amazon"},
            "extract": {
                "order_number": {
                    "method": "regex",
                    "pattern": "Order\\s*#\\s*([0-9-]{10,})",
                    "transforms": ["trim", "normalize_order_number"],
                },
                "order_action_url": {
                    "method": "link_by_type",
                    "link_type": "order_action",
                    "transforms": ["normalize_url"],
                },
            },
            "required_fields": ["order_number"],
            "confidence_rules": {"high_requires": ["order_number"]},
            "post_process": {},
        }
    )

    assert payload.match.vendor_identity == "amazon"
    assert payload.extract["order_number"].method == "regex"


def test_pattern_generation_response_rejects_extra_top_level_keys():
    with pytest.raises(ValidationError):
        PatternGenerationResponse.model_validate(
            {
                "schema_version": "order-phase4-template.v1",
                "template_id": "amazon_order_confirmation.v1",
                "profile_id": "amazon_order_confirmation",
                "template_version": "v1",
                "enabled": True,
                "match": {"vendor_identity": "amazon"},
                "extract": {},
                "required_fields": [],
                "confidence_rules": {"high_requires": []},
                "post_process": {},
                "extra_key": True,
            }
        )


def test_pattern_generation_response_rejects_missing_vendor_identity():
    with pytest.raises(ValidationError):
        PatternGenerationResponse.model_validate(
            {
                "schema_version": "order-phase4-template.v1",
                "template_id": "amazon_order_confirmation.v1",
                "profile_id": "amazon_order_confirmation",
                "template_version": "v1",
                "enabled": True,
                "match": {},
                "extract": {},
                "required_fields": [],
                "confidence_rules": {"high_requires": []},
                "post_process": {},
            }
        )


def test_pattern_generation_response_rejects_invalid_extract_rule_shape():
    with pytest.raises(ValidationError):
        PatternGenerationResponse.model_validate(
            {
                "schema_version": "order-phase4-template.v1",
                "template_id": "amazon_order_confirmation.v1",
                "profile_id": "amazon_order_confirmation",
                "template_version": "v1",
                "enabled": True,
                "match": {"vendor_identity": "amazon"},
                "extract": {
                    "order_number": {
                        "method": "regex"
                    }
                },
                "required_fields": ["order_number"],
                "confidence_rules": {"high_requires": ["order_number"]},
                "post_process": {},
            }
        )
