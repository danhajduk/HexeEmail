from __future__ import annotations

from email_node.pipeline import OrderActionGate, OrderDecisionResult
from tests.test_order_probation_pipeline import build_unresolved_phase4


def test_order_action_gate_allows_active_accept_results():
    gate = OrderActionGate()
    phase4 = build_unresolved_phase4().model_copy(update={"extracted_fields": {"order_number": {"value": "123"}}})
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

    result = gate.authorize(decision=decision, phase4=phase4)

    assert result.actions_allowed is True
    assert result.blocked_reason is None


def test_order_action_gate_blocks_probation_results():
    gate = OrderActionGate()
    phase4 = build_unresolved_phase4().model_copy(update={"extracted_fields": {"order_number": {"value": "123"}}})
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

    result = gate.authorize(decision=decision, phase4=phase4)

    assert result.actions_allowed is False
    assert result.blocked_reason == "decision_probation"


def test_order_action_gate_blocks_reject_results():
    gate = OrderActionGate()
    phase4 = build_unresolved_phase4()
    decision = OrderDecisionResult(
        decision="reject",
        decision_reason="no_structured_extraction",
        allow_persist_structured_result=False,
        allow_downstream_actions=False,
        requires_manual_review=True,
        confidence=0.0,
        confidence_level="low",
        extraction_source="active",
        profile_id=None,
        diagnostics=["decision:reject"],
    )

    result = gate.authorize(decision=decision, phase4=phase4)

    assert result.actions_allowed is False
    assert result.blocked_reason == "decision_reject:no_structured_extraction"
