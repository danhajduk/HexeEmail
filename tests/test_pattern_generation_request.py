from __future__ import annotations

import pytest
from pydantic import ValidationError

from email_node.patterns.pattern_generation_request import PatternGenerationRequest


def test_pattern_generation_request_accepts_valid_input_and_applies_defaults():
    payload = PatternGenerationRequest(
        template_id="amazon_order_confirmation.v1",
        profile_id="amazon_order_confirmation",
        vendor_identity="amazon",
        expected_label="order",
        from_name="Amazon",
        from_email="auto-confirm@amazon.com",
        subject="Your Amazon order",
        received_at="2026-04-05T13:00:00Z",
        body_text="Order # 123-1234567-1234567",
    )

    assert payload.template_version == "v1"
    assert payload.expected_label == "ORDER"
    assert payload.body_html == ""
    assert payload.links_json == []


def test_pattern_generation_request_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        PatternGenerationRequest(
            template_id="amazon_order_confirmation.v1",
            profile_id="amazon_order_confirmation",
            vendor_identity="amazon",
            expected_label="ORDER",
            from_name="Amazon",
            from_email="auto-confirm@amazon.com",
            subject="Your Amazon order",
            received_at="2026-04-05T13:00:00Z",
        )


def test_pattern_generation_request_rejects_empty_body_text():
    with pytest.raises(ValidationError, match="body_text must not be empty"):
        PatternGenerationRequest(
            template_id="amazon_order_confirmation.v1",
            profile_id="amazon_order_confirmation",
            vendor_identity="amazon",
            expected_label="ORDER",
            from_name="Amazon",
            from_email="auto-confirm@amazon.com",
            subject="Your Amazon order",
            received_at="2026-04-05T13:00:00Z",
            body_text="   ",
        )


def test_pattern_generation_request_rejects_empty_template_and_profile_ids():
    with pytest.raises(ValidationError):
        PatternGenerationRequest(
            template_id=" ",
            profile_id=" ",
            vendor_identity="amazon",
            expected_label="ORDER",
            from_name="Amazon",
            from_email="auto-confirm@amazon.com",
            subject="Your Amazon order",
            received_at="2026-04-05T13:00:00Z",
            body_text="Order body",
        )
