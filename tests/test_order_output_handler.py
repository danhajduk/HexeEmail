from __future__ import annotations

import json
from pathlib import Path

from email_node.pipeline import OrderDecisionResult, OrderOutputHandler
from tests.test_order_probation_pipeline import build_unresolved_phase4


def test_order_output_handler_persists_trusted_accept_record(tmp_path: Path):
    handler = OrderOutputHandler(runtime_dir=tmp_path / "runtime")
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "extraction_status": "success",
            "template_id": "amazon_order_confirmation.v1",
            "profile_id": "amazon_order_confirmation",
            "extraction_confidence": 0.95,
            "extraction_confidence_level": "high",
            "extracted_fields": {
                "order_number": build_unresolved_phase4().extracted_fields.get("order_number")
                if build_unresolved_phase4().extracted_fields
                else {},
            },
        }
    )
    decision = OrderDecisionResult(
        decision="accept",
        decision_reason="active_high_confidence",
        allow_persist_structured_result=True,
        allow_downstream_actions=True,
        requires_manual_review=False,
        confidence=0.95,
        confidence_level="high",
        extraction_source="active",
        profile_id="amazon_order_confirmation",
        diagnostics=["decision:accept"],
    )

    result = handler.persist(decision=decision, phase4=phase4)

    assert result.persisted is True
    assert result.trust_level == "trusted"
    assert result.record_path is not None
    payload = json.loads(Path(result.record_path).read_text())
    assert payload["trust_level"] == "trusted"
    assert payload["decision"] == "accept"
    assert payload["profile_id"] == "amazon_order_confirmation"


def test_order_output_handler_persists_probation_record_as_partial(tmp_path: Path):
    handler = OrderOutputHandler(runtime_dir=tmp_path / "runtime")
    phase4 = build_unresolved_phase4()
    decision = OrderDecisionResult(
        decision="probation",
        decision_reason="probation_template_result",
        allow_persist_structured_result=True,
        allow_downstream_actions=False,
        requires_manual_review=True,
        confidence=0.49,
        confidence_level="low",
        extraction_source="probation",
        profile_id="reservation_confirmation",
        diagnostics=["decision:probation"],
    )

    result = handler.persist(decision=decision, phase4=phase4)

    assert result.persisted is True
    assert result.trust_level == "partial"
    assert result.record_path is not None
    payload = json.loads(Path(result.record_path).read_text())
    assert payload["trust_level"] == "partial"
    assert payload["decision"] == "probation"


def test_order_output_handler_persists_review_needed_record(tmp_path: Path):
    handler = OrderOutputHandler(runtime_dir=tmp_path / "runtime")
    phase4 = build_unresolved_phase4()
    decision = OrderDecisionResult(
        decision="review_needed",
        decision_reason="no_structured_extraction",
        allow_persist_structured_result=True,
        allow_downstream_actions=True,
        requires_manual_review=True,
        confidence=0.0,
        confidence_level="low",
        extraction_source="active",
        profile_id=None,
        diagnostics=["decision:review_needed"],
    )

    result = handler.persist(decision=decision, phase4=phase4)

    assert result.persisted is True
    assert result.trust_level == "review_needed"
    assert result.record_path is not None
    payload = json.loads(Path(result.record_path).read_text())
    assert payload["trust_level"] == "review_needed"
    assert payload["decision"] == "review_needed"
