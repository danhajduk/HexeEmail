from __future__ import annotations

import pytest

from email_node.patterns.pattern_generation_request import PatternGenerationRequest
from email_node.patterns.pattern_generation_response import PatternGenerationResponse
from email_node.patterns.pattern_generation_service import PatternGenerationService, PatternGenerationServiceError


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


def build_template() -> PatternGenerationResponse:
    return PatternGenerationResponse.model_validate(
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
        }
    )


class FakePipeline:
    def __init__(self, template=None, error: Exception | None = None):
        self.template = template
        self.error = error

    async def generate_template(self, request: PatternGenerationRequest):
        if self.error is not None:
            raise self.error
        return self.template


class FakeWriter:
    def __init__(self, output_path: str = "/tmp/template.json", error: Exception | None = None):
        self.output_path = output_path
        self.error = error

    def write_template(self, template: PatternGenerationResponse, *, allow_overwrite: bool = False):
        if self.error is not None:
            raise self.error
        return self.output_path


@pytest.mark.asyncio
async def test_pattern_generation_service_runs_end_to_end():
    service = PatternGenerationService(FakePipeline(template=build_template()), FakeWriter())

    result = await service.generate(build_request())

    assert result == {
        "ok": True,
        "template_id": "amazon_order_confirmation.v1",
        "file_path": "/tmp/template.json",
    }


@pytest.mark.asyncio
async def test_pattern_generation_service_returns_structured_error():
    service = PatternGenerationService(FakePipeline(error=RuntimeError("bad ai output")), FakeWriter())

    with pytest.raises(PatternGenerationServiceError, match="bad ai output"):
        await service.generate(build_request())
