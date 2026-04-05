from __future__ import annotations

import pytest

from email_node.patterns.pattern_generation_pipeline import PatternGenerationPipeline, PatternGenerationPipelineError
from email_node.patterns.pattern_generation_request import PatternGenerationRequest


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    async def generate_pattern(self, request: PatternGenerationRequest):
        return self.payload


def build_request() -> PatternGenerationRequest:
    return PatternGenerationRequest(
        template_id="amazon_order_confirmation.v1",
        profile_id="amazon_order_confirmation",
        vendor_identity="amazon",
        expected_label="ORDER",
        from_name="Amazon",
        from_email="auto-confirm@amazon.com",
        subject="Your Amazon order",
        received_at="2026-04-05T13:00:00Z",
        body_text="Order # 123-1234567-1234567",
    )


@pytest.mark.asyncio
async def test_pattern_generation_pipeline_returns_validated_template():
    pipeline = PatternGenerationPipeline(
        FakeClient(
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
                    }
                },
                "required_fields": ["order_number"],
                "confidence_rules": {"high_requires": ["order_number"]},
                "post_process": {},
            }
        )
    )

    result = await pipeline.generate_template(build_request())

    assert result.template_id == "amazon_order_confirmation.v1"


@pytest.mark.asyncio
async def test_pattern_generation_pipeline_normalizes_null_arrays_and_post_process():
    pipeline = PatternGenerationPipeline(
        FakeClient(
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
                        "transforms": None,
                    }
                },
                "required_fields": None,
                "confidence_rules": {"high_requires": None},
                "post_process": None,
            }
        )
    )

    result = await pipeline.generate_template(build_request())

    assert result.required_fields == []
    assert result.confidence_rules.high_requires == []
    assert result.post_process == {}
    assert result.extract["order_number"].transforms == []


@pytest.mark.asyncio
async def test_pattern_generation_pipeline_fails_on_schema_mismatch():
    pipeline = PatternGenerationPipeline(
        FakeClient(
            {
                "schema_version": "order-phase4-template.v1",
                "template_id": "amazon_order_confirmation.v1",
                "profile_id": "amazon_order_confirmation",
                "template_version": "v2",
                "enabled": True,
                "match": {"vendor_identity": "amazon"},
                "extract": {},
                "required_fields": [],
                "confidence_rules": {"high_requires": []},
                "post_process": {},
            }
        )
    )

    with pytest.raises(PatternGenerationPipelineError, match="schema validation"):
        await pipeline.generate_template(build_request())
