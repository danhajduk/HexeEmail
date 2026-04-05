from __future__ import annotations

import json

import pytest

from scripts.generate_pattern import run_cli


class FakeService:
    async def generate(self, request, *, allow_overwrite: bool = False):
        return {
            "ok": True,
            "template_id": request.template_id,
            "file_path": "/tmp/generated-template.json",
        }


def fake_service_factory(*, target_api_base_url: str):
    assert target_api_base_url == "http://127.0.0.1:9002"
    return FakeService()


@pytest.mark.asyncio
async def test_generate_pattern_script_reports_success(tmp_path, capsys):
    input_path = tmp_path / "sample.json"
    input_path.write_text(
        json.dumps(
            {
                "template_id": "amazon_order_confirmation.v1",
                "profile_id": "amazon_order_confirmation",
                "vendor_identity": "amazon",
                "expected_label": "ORDER",
                "from_name": "Amazon",
                "from_email": "auto-confirm@amazon.com",
                "subject": "Your Amazon order",
                "received_at": "2026-04-05T13:00:00Z",
                "body_text": "Order # 123-1234567-1234567",
            }
        ),
        encoding="utf-8",
    )

    exit_code = await run_cli(["--input", str(input_path)], service_factory=fake_service_factory)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "SUCCESS: amazon_order_confirmation.v1 -> /tmp/generated-template.json" in captured.out


@pytest.mark.asyncio
async def test_generate_pattern_script_reports_error(tmp_path, capsys):
    input_path = tmp_path / "sample.json"
    input_path.write_text("{\"not\": \"valid for request\"}", encoding="utf-8")

    exit_code = await run_cli(["--input", str(input_path)], service_factory=fake_service_factory)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR:" in captured.out
