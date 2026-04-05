from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_pattern_generation_api_triggers_service_flow(config, core_client_factory, monkeypatch):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    async def fake_generate_pattern_template(payload):
        return {
            "ok": True,
            "template_id": payload.template_id,
            "file_path": "/tmp/generated-template.json",
        }

    monkeypatch.setattr(service, "generate_pattern_template", fake_generate_pattern_template)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/patterns/generate",
            json={
                "template_id": "amazon_order_confirmation.v1",
                "profile_id": "amazon_order_confirmation",
                "vendor_identity": "amazon",
                "expected_label": "ORDER",
                "from_name": "Amazon",
                "from_email": "auto-confirm@amazon.com",
                "subject": "Your Amazon order",
                "received_at": "2026-04-05T13:00:00Z",
                "body_text": "Order # 123-1234567-1234567",
            },
        )

    await service.stop()

    assert response.status_code == 200
    assert response.json()["template_id"] == "amazon_order_confirmation.v1"


@pytest.mark.asyncio
async def test_pattern_generation_api_returns_400_for_generation_error(config, core_client_factory, monkeypatch):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    async def fake_generate_pattern_template(payload):
        raise ValueError("generation failed")

    monkeypatch.setattr(service, "generate_pattern_template", fake_generate_pattern_template)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/patterns/generate",
            json={
                "template_id": "amazon_order_confirmation.v1",
                "profile_id": "amazon_order_confirmation",
                "vendor_identity": "amazon",
                "expected_label": "ORDER",
                "from_name": "Amazon",
                "from_email": "auto-confirm@amazon.com",
                "subject": "Your Amazon order",
                "received_at": "2026-04-05T13:00:00Z",
                "body_text": "Order # 123-1234567-1234567",
            },
        )

    await service.stop()

    assert response.status_code == 400
    assert response.json()["detail"] == "generation failed"
