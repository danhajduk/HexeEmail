from __future__ import annotations

import json

import pytest

from email_node.patterns.pattern_generation_response import PatternGenerationResponse
from email_node.patterns.pattern_generation_writer import PatternGenerationWriter, PatternGenerationWriterError


def build_template() -> PatternGenerationResponse:
    return PatternGenerationResponse.model_validate(
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


def test_pattern_generation_writer_saves_pretty_json(tmp_path):
    writer = PatternGenerationWriter(base_dir=tmp_path)

    output_path = writer.write_template(build_template())

    assert output_path.name == "amazon_order_confirmation.v1.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["template_id"] == "amazon_order_confirmation.v1"


def test_pattern_generation_writer_rejects_overwrite_by_default(tmp_path):
    writer = PatternGenerationWriter(base_dir=tmp_path)
    template = build_template()
    writer.write_template(template)

    with pytest.raises(PatternGenerationWriterError, match="already exists"):
        writer.write_template(template)


def test_pattern_generation_writer_allows_overwrite_when_enabled(tmp_path):
    writer = PatternGenerationWriter(base_dir=tmp_path)
    template = build_template()
    writer.write_template(template)

    output_path = writer.write_template(template, allow_overwrite=True)

    assert output_path.exists()
