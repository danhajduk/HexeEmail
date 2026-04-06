from __future__ import annotations

from email_node.actions import TrackingMonitorHandler
from email_node.pipeline import OrderActionRoutingResult, OrderDecisionResult
from tests.test_order_probation_pipeline import build_unresolved_phase4


def test_tracking_monitor_handler_builds_request_for_accepted_tracking_result():
    handler = TrackingMonitorHandler()
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "generic_order_status_update",
            "extracted_fields": {
                "order_number": {"value": "112-1234567-1234567"},
                "tracking_number": {"value": "TRACK123"},
                "carrier": {"value": "ups"},
                "status": {"value": "Out for delivery"},
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
        profile_id="generic_order_status_update",
        diagnostics=["decision:accept"],
    )
    routing = OrderActionRoutingResult(action_intents=["queue_tracking_monitor"], diagnostics=[])

    result = handler.build_request(decision=decision, action_routing=routing, phase4=phase4)

    assert result.queued is True
    assert result.payload is not None
    assert result.payload["tracking_number"] == "TRACK123"


def test_tracking_monitor_handler_blocks_without_tracking_identity():
    handler = TrackingMonitorHandler()
    decision = OrderDecisionResult(
        decision="accept",
        decision_reason="active_high_confidence",
        allow_persist_structured_result=True,
        allow_downstream_actions=True,
        requires_manual_review=False,
        confidence=0.95,
        confidence_level="high",
        extraction_source="active",
        profile_id="generic_order_status_update",
        diagnostics=["decision:accept"],
    )
    routing = OrderActionRoutingResult(action_intents=["queue_tracking_monitor"], diagnostics=[])

    result = handler.build_request(decision=decision, action_routing=routing, phase4=build_unresolved_phase4())

    assert result.queued is False
    assert result.blocked_reason == "insufficient_tracking_identity"


def test_tracking_monitor_handler_blocks_probation_results():
    handler = TrackingMonitorHandler()
    decision = OrderDecisionResult(
        decision="probation",
        decision_reason="probation_template_result",
        allow_persist_structured_result=True,
        allow_downstream_actions=False,
        requires_manual_review=True,
        confidence=0.49,
        confidence_level="low",
        extraction_source="probation",
        profile_id="generic_order_status_update",
        diagnostics=["decision:probation"],
    )
    routing = OrderActionRoutingResult(action_intents=["queue_tracking_monitor"], diagnostics=[])

    result = handler.build_request(decision=decision, action_routing=routing, phase4=build_unresolved_phase4())

    assert result.queued is False
    assert result.blocked_reason == "decision:probation"
