from __future__ import annotations

from httpx import ASGITransport, AsyncClient
import pytest

from main import create_app
from service import NodeService
from tests.helpers import FakeMQTTManager, build_core_app


@pytest.mark.asyncio
async def test_probation_api_lists_templates(config, core_client_factory, monkeypatch):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    monkeypatch.setattr(service, "list_probation_templates", lambda: {"items": [{"state": {"template_id": "t1"}}]})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/patterns/probation")

    await service.stop()

    assert response.status_code == 200
    assert response.json()["items"][0]["state"]["template_id"] == "t1"


@pytest.mark.asyncio
async def test_probation_api_reads_single_template_and_evaluations(config, core_client_factory, monkeypatch):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    app = create_app(config=config, service=service)

    monkeypatch.setattr(service, "get_probation_template", lambda template_id: {"state": {"template_id": template_id}})
    monkeypatch.setattr(service, "list_probation_evaluations", lambda template_id: {"items": [{"message_id": "m1"}], "shadow": []})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        template_response = await client.get("/api/patterns/probation/template-1")
        evaluations_response = await client.get("/api/patterns/probation/template-1/evaluations")

    await service.stop()

    assert template_response.status_code == 200
    assert template_response.json()["state"]["template_id"] == "template-1"
    assert evaluations_response.status_code == 200
    assert evaluations_response.json()["items"][0]["message_id"] == "m1"
