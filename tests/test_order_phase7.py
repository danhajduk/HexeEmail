from __future__ import annotations

import asyncio
from email_node.pipeline import OrderFlowPipeline
from email_node.patterns import ProbationStore, ProbationTemplateState
from tests.test_order_probation_pipeline import build_phase2_payload, build_unresolved_phase4
from datetime import UTC, datetime


def test_phase7_accept_result_persists_and_allows_actions(tmp_path):
    class StubPhase2Scrubber:
        def scrub(self, _normalized):
            return build_phase2_payload()

    class StubPhase3Detector:
        def detect(self, phase2):
            return build_unresolved_phase4().phase3_reference

    class StubPhase4Extractor:
        def extract(self, _phase3):
            return build_unresolved_phase4().model_copy(
                update={
                    "profile_id": "amazon_order_confirmation",
                    "template_id": "amazon_order_confirmation.v1",
                    "extraction_status": "success",
                    "extraction_confidence": 0.95,
                    "extraction_confidence_level": "high",
                    "template_diagnostics": ["template_lookup:resolved:amazon_order_confirmation.v1"],
                    "extracted_fields": {
                        "order_number": {"value": "112-1234567-1234567"},
                        "tracking_number": {"value": "TRACK123"},
                        "carrier": {"value": "ups"},
                    },
                }
            )

    output = asyncio.run(
        OrderFlowPipeline(
            phase2_scrubber=StubPhase2Scrubber(),
            phase3_detector=StubPhase3Detector(),
            phase4_extractor=StubPhase4Extractor(),
            runtime_dir=tmp_path / "runtime",
        ).process_normalized_email(object())
    )

    assert output["phase7_result"]["persisted_result"] is True
    assert output["phase7_result"]["actions_allowed"] is True


async def _probation_pipeline_result(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
    )
    template_id = "recreation_gov_reservation_confirmation.v1"
    store.save_template_payload(
        template_id,
        {
            "schema_version": "order-phase4-template.v1",
            "template_id": template_id,
            "profile_id": "reservation_confirmation",
            "template_version": "v1",
            "enabled": True,
            "match": {"vendor_identity": "recreation_gov"},
            "extract": {
                "order_number": {
                    "method": "line_after",
                    "marker": "transaction details",
                    "transforms": ["trim", "normalize_order_number"],
                },
            },
            "required_fields": ["order_number"],
            "confidence_rules": {"high_requires": ["order_number"]},
            "post_process": {},
        },
    )
    store.save_state(
        ProbationTemplateState(
            template_id=template_id,
            profile_id="reservation_confirmation",
            template_version="v1",
            created_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
        )
    )

    class StubPhase2Scrubber:
        def scrub(self, _normalized):
            return build_phase2_payload()

    pipeline = OrderFlowPipeline(
        phase2_scrubber=StubPhase2Scrubber(),
        probation_store=store,
        generate_probation_template=None,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
        runtime_dir=tmp_path / "runtime",
    )
    return await pipeline.process_normalized_email(object())


def test_phase7_probation_result_blocks_actions(tmp_path):
    result = asyncio.run(_probation_pipeline_result(tmp_path))

    assert result["phase7_result"]["persisted_result"] is True
    assert result["phase7_result"]["actions_allowed"] is False
    assert result["user_notification"].queued is False
