from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from email_node.patterns.pattern_generation_client import PatternGenerationClient
from email_node.patterns.pattern_generation_pipeline import PatternGenerationPipeline, PatternGenerationPipelineError
from email_node.patterns.pattern_generation_request import PatternGenerationRequest
from email_node.patterns.pattern_generation_service import PatternGenerationService
from email_node.patterns.pattern_generation_writer import PatternGenerationWriter


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


def write_prompt_definition(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "prompt_id": "prompt.email.order_pattern_template_creation",
                "service_id": "node-email",
                "task_family": "task.structured_extraction",
                "version": "v1.0",
                "node_runtime": {
                    "timeout_s": 45,
                    "json_schema": {
                        "type": "object",
                        "properties": {"template_id": {"type": "string"}},
                        "required": ["template_id"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def build_service(tmp_path: Path, handler) -> PatternGenerationService:
    prompt_path = tmp_path / "prompt.json"
    write_prompt_definition(prompt_path)
    client = PatternGenerationClient(
        target_api_base_url="http://127.0.0.1:9002",
        prompt_definition_path=prompt_path,
        transport=httpx.MockTransport(handler),
    )
    pipeline = PatternGenerationPipeline(client)
    writer = PatternGenerationWriter(base_dir=tmp_path / "draft")
    return PatternGenerationService(pipeline, writer)


@pytest.mark.asyncio
async def test_pattern_generation_valid_generation_flow(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": {
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
                },
            },
        )

    service = build_service(tmp_path, handler)

    result = await service.generate(build_request())

    assert result["ok"] is True
    assert result["template_id"] == "amazon_order_confirmation.v1"
    assert Path(result["file_path"]).exists()


@pytest.mark.asyncio
async def test_pattern_generation_invalid_json_response_fails(tmp_path):
    service = build_service(
        tmp_path,
        lambda request: httpx.Response(200, json={"status": "completed", "output": "not json"}),
    )

    with pytest.raises(Exception):
        await service.generate(build_request())


@pytest.mark.asyncio
async def test_pattern_generation_schema_validation_failure_fails(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": {
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
                },
            },
        )

    service = build_service(tmp_path, handler)

    with pytest.raises(PatternGenerationPipelineError):
        await service.pipeline.generate_template(build_request())


@pytest.mark.asyncio
async def test_pattern_generation_file_write_success(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": {
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
                },
            },
        )

    service = build_service(tmp_path, handler)

    result = await service.generate(build_request())
    output_path = Path(result["file_path"])

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["template_id"] == "amazon_order_confirmation.v1"
