from __future__ import annotations

from email_node.pipeline.order_decision_engine import OrderDecisionEngine
from tests.test_order_probation_pipeline import build_unresolved_phase4


def test_order_decision_engine_accepts_high_confidence_active_result():
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "template_id": "active-template.v1",
            "extraction_status": "success",
            "extraction_confidence": 0.92,
            "extraction_confidence_level": "high",
            "extracted_fields": {"order_number": object()},
            "template_diagnostics": ["template_lookup:matched:active-template.v1"],
            "field_diagnostics": [],
        }
    )

    result = OrderDecisionEngine().decide(phase4)

    assert result.decision == "accept"
    assert result.allow_persist_structured_result is True
    assert result.allow_downstream_actions is True
    assert result.requires_manual_review is False
    assert result.extraction_source == "active"


def test_order_decision_engine_probations_medium_confidence_active_result():
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "template_id": "active-template.v1",
            "extraction_status": "partial",
            "extraction_confidence": 0.71,
            "extraction_confidence_level": "medium",
            "extracted_fields": {"order_number": object()},
            "template_diagnostics": ["confidence_downgrade:missing_required_fields"],
            "field_diagnostics": ["missing_required:total"],
        }
    )

    result = OrderDecisionEngine().decide(phase4)

    assert result.decision == "probation"
    assert result.allow_persist_structured_result is True
    assert result.allow_downstream_actions is False
    assert result.requires_manual_review is True
    assert result.decision_reason == "active_medium_confidence"


def test_order_decision_engine_rejects_hard_validation_failure():
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "template_id": "active-template.v1",
            "extraction_status": "partial",
            "extraction_confidence": 0.93,
            "extraction_confidence_level": "high",
            "extracted_fields": {"order_action_url": object()},
            "field_diagnostics": ["invalid_field:order_action_url"],
        }
    )

    result = OrderDecisionEngine().decide(phase4)

    assert result.decision == "reject"
    assert result.allow_persist_structured_result is False
    assert result.allow_downstream_actions is False
    assert result.requires_manual_review is True
    assert result.decision_reason == "hard_validation_failure"


def test_order_decision_engine_keeps_probation_results_non_actionable():
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "template_id": "probation-template.v1",
            "extraction_status": "partial",
            "extraction_confidence": 0.49,
            "extraction_confidence_level": "low",
            "extracted_fields": {"order_number": object()},
            "template_diagnostics": ["probation_template:applied:probation-template.v1"],
            "field_diagnostics": [],
        }
    )

    result = OrderDecisionEngine().decide(phase4)

    assert result.decision == "probation"
    assert result.allow_persist_structured_result is True
    assert result.allow_downstream_actions is False
    assert result.requires_manual_review is True
    assert result.extraction_source == "probation"
