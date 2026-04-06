from __future__ import annotations

import json

import httpx
import pytest

from email_node.patterns.pattern_generation_client import PatternGenerationClient, PatternGenerationClientError
from email_node.patterns.pattern_generation_request import PatternGenerationRequest


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


def build_prompt_definition() -> dict[str, object]:
    return {
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


@pytest.mark.asyncio
async def test_pattern_generation_client_calls_ai_node_and_returns_parsed_json(tmp_path):
    prompt_path = tmp_path / "prompt.json"
    prompt_path.write_text(json.dumps(build_prompt_definition()), encoding="utf-8")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.read().decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": "{\"template_id\":\"amazon_order_confirmation.v1\"}",
            },
        )

    client = PatternGenerationClient(
        target_api_base_url="http://127.0.0.1:9002",
        prompt_definition_path=prompt_path,
        transport=httpx.MockTransport(handler),
    )

    result = await client.generate_pattern(build_request())

    assert seen["url"] == "http://127.0.0.1:9002/api/execution/direct"
    assert seen["body"]["prompt_id"] == "prompt.email.order_pattern_template_creation"
    assert seen["body"]["inputs"]["template_id"] == "amazon_order_confirmation.v1"
    assert result == {"template_id": "amazon_order_confirmation.v1"}


@pytest.mark.asyncio
async def test_pattern_generation_client_unwraps_text_wrapped_json_object(tmp_path):
    prompt_path = tmp_path / "prompt.json"
    prompt_path.write_text(json.dumps(build_prompt_definition()), encoding="utf-8")

    client = PatternGenerationClient(
        target_api_base_url="http://127.0.0.1:9002",
        prompt_definition_path=prompt_path,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": {
                        "text": "{\"template_id\":\"wrapped-success\"}",
                    },
                },
            )
        ),
    )

    result = await client.generate_pattern(build_request())

    assert result == {"template_id": "wrapped-success"}


@pytest.mark.asyncio
async def test_pattern_generation_client_retries_once_when_json_parse_fails(tmp_path):
    prompt_path = tmp_path / "prompt.json"
    prompt_path.write_text(json.dumps(build_prompt_definition()), encoding="utf-8")
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, json={"status": "completed", "output": "```json\n{}\n```"})
        return httpx.Response(200, json={"status": "completed", "output": "{\"template_id\":\"retry-success\"}"})

    client = PatternGenerationClient(
        target_api_base_url="http://127.0.0.1:9002",
        prompt_definition_path=prompt_path,
        transport=httpx.MockTransport(handler),
    )

    result = await client.generate_pattern(build_request())

    assert calls["count"] == 2
    assert result == {"template_id": "retry-success"}


@pytest.mark.asyncio
async def test_pattern_generation_client_raises_after_retry_exhausted(tmp_path):
    prompt_path = tmp_path / "prompt.json"
    prompt_path.write_text(json.dumps(build_prompt_definition()), encoding="utf-8")

    client = PatternGenerationClient(
        target_api_base_url="http://127.0.0.1:9002",
        prompt_definition_path=prompt_path,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "completed", "output": "not json"})),
    )

    with pytest.raises(PatternGenerationClientError, match="JSON only"):
        await client.generate_pattern(build_request())


@pytest.mark.asyncio
async def test_pattern_generation_client_selects_action_required_prompt_from_expected_label(tmp_path):
    prompt_path = tmp_path / "action_required_prompt.json"
    prompt_path.write_text(
        json.dumps(
            {
                **build_prompt_definition(),
                "prompt_id": "prompt.email.action_required_pattern_template_creation",
            }
        ),
        encoding="utf-8",
    )
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.read().decode("utf-8"))
        return httpx.Response(200, json={"status": "completed", "output": "{\"template_id\":\"site_issue_action_required.v1\"}"})

    client = PatternGenerationClient(
        target_api_base_url="http://127.0.0.1:9002",
        prompt_definition_path=prompt_path,
        transport=httpx.MockTransport(handler),
    )

    result = await client.generate_pattern(
        PatternGenerationRequest(
            template_id="site_issue_action_required.v1",
            profile_id="site_issue_action_required",
            vendor_identity="google",
            expected_label="ACTION_REQUIRED",
            from_name="Google Search Console Team",
            from_email="sc-noreply@google.com",
            subject="New reasons prevent pages from being indexed",
            received_at="2026-04-06T13:00:00Z",
            body_text="New reasons prevent pages from being indexed.",
        )
    )

    assert seen["body"]["prompt_id"] == "prompt.email.action_required_pattern_template_creation"
    assert result == {"template_id": "site_issue_action_required.v1"}
