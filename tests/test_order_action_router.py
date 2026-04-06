from __future__ import annotations

from email_node.pipeline import (
    OrderActionAuthorizationResult,
    OrderActionRouter,
    OrderDecisionResult,
)
from tests.test_order_probation_pipeline import build_unresolved_phase4


def test_order_action_router_returns_store_and_notify_for_accepted_confirmation():
    router = OrderActionRouter()
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "amazon_order_confirmation",
            "extracted_fields": {"order_number": {"value": "112-1234567-1234567"}},
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
    authorization = OrderActionAuthorizationResult(
        actions_allowed=True,
        decision="accept",
        extraction_source="active",
        diagnostics=["action_gate:allowed"],
    )

    result = router.route(decision=decision, authorization=authorization, phase4=phase4)

    assert result.action_intents == ["store_order_record", "user_notification"]


def test_order_action_router_returns_tracking_intents_for_status_update():
    router = OrderActionRouter()
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "generic_order_status_update",
            "extracted_fields": {
                "tracking_number": {"value": "TRACK123"},
                "carrier": {"value": "ups"},
                "order_number": {"value": "112-1234567-1234567"},
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
    authorization = OrderActionAuthorizationResult(
        actions_allowed=True,
        decision="accept",
        extraction_source="active",
        diagnostics=["action_gate:allowed"],
    )

    result = router.route(decision=decision, authorization=authorization, phase4=phase4)

    assert result.action_intents == [
        "update_order_record",
        "attach_tracking_reference",
        "queue_tracking_monitor",
        "user_notification",
    ]


def test_order_action_router_returns_no_actions_when_blocked():
    router = OrderActionRouter()
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
    authorization = OrderActionAuthorizationResult(
        actions_allowed=False,
        blocked_reason="decision_probation",
        decision="probation",
        extraction_source="probation",
        diagnostics=["action_gate:blocked:decision_probation"],
    )

    result = router.route(decision=decision, authorization=authorization, phase4=phase4)

    assert result.action_intents == []
