from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from node_backend.ai_gateway import AiNodeGateway
from node_backend.email_provider_gateway import EmailProviderGateway


@pytest.mark.asyncio
async def test_ai_gateway_get_prompt_service_returns_none_for_unregistered_400():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://node.test/api/prompts/services/prompt.email.classifier"
        return httpx.Response(400, json={"detail": "prompt_id is not registered"})

    service = SimpleNamespace(
        runtime=SimpleNamespace(
            runtime_ai_calls_enabled=lambda: True,
            runtime_ai_disabled_message=lambda: "AI calls are disabled in Runtime Settings.",
            normalize_target_api_base_url=lambda value: value or "http://node.test",
        ),
        core_client=SimpleNamespace(timeout=10.0, transport=httpx.MockTransport(handler)),
    )
    gateway = AiNodeGateway(service)

    result = await gateway.get_prompt_service("http://node.test", prompt_id="prompt.email.classifier")

    assert result is None


@pytest.mark.asyncio
async def test_ai_gateway_execute_direct_rejects_when_disabled():
    service = SimpleNamespace(
        runtime=SimpleNamespace(
            runtime_ai_calls_enabled=lambda: False,
            runtime_ai_disabled_message=lambda: "AI calls are disabled in Runtime Settings.",
            normalize_target_api_base_url=lambda value: value or "http://node.test",
        ),
        core_client=SimpleNamespace(timeout=10.0, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))),
    )
    gateway = AiNodeGateway(service)

    with pytest.raises(ValueError, match="AI calls are disabled in Runtime Settings."):
        await gateway.execute_direct("http://node.test", request_body={"prompt_id": "prompt.email.classifier"})


@pytest.mark.asyncio
async def test_email_provider_gateway_blocks_remote_fetch_when_disabled():
    state = {"called": False}

    class FakeAdapter:
        async def fetch_full_message_payload(self, account_id: str, message_id: str) -> dict[str, object]:
            state["called"] = True
            return {"account_id": account_id, "message_id": message_id}

    service = SimpleNamespace(
        runtime=SimpleNamespace(
            runtime_provider_calls_enabled=lambda: False,
            runtime_provider_disabled_message=lambda: "Provider calls are disabled in Runtime Settings.",
        ),
        provider_registry=SimpleNamespace(get_provider=lambda provider_id: FakeAdapter()),
    )
    gateway = EmailProviderGateway(service)

    with pytest.raises(ValueError, match="Provider calls are disabled in Runtime Settings."):
        await gateway.gmail_fetch_full_message_payload("primary", "msg-1")

    assert state["called"] is False
