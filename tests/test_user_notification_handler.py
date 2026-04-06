from __future__ import annotations

from email_node.actions import UserNotificationHandler
from email_node.pipeline import OrderActionRoutingResult, OrderDecisionResult
from tests.test_order_probation_pipeline import build_unresolved_phase4


def test_user_notification_handler_builds_reservation_confirmation_message():
    handler = UserNotificationHandler()
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "reservation_confirmation",
            "extracted_fields": {"order_number": {"value": "0892885499"}},
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
        profile_id="reservation_confirmation",
        diagnostics=["decision:accept"],
    )
    routing = OrderActionRoutingResult(action_intents=["store_order_record", "user_notification"], diagnostics=[])

    result = handler.build_request(decision=decision, action_routing=routing, phase4=phase4)

    assert result.queued is True
    assert result.title == "Reservation confirmed"
    assert "0892885499" in (result.message or "")


def test_user_notification_handler_builds_status_update_message():
    handler = UserNotificationHandler()
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "generic_order_status_update",
            "extracted_fields": {
                "status": {"value": "Your package is out for delivery."},
                "tracking_number": {"value": "TRACK123"},
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
    routing = OrderActionRoutingResult(action_intents=["update_order_record", "user_notification"], diagnostics=[])

    result = handler.build_request(decision=decision, action_routing=routing, phase4=phase4)

    assert result.queued is True
    assert result.title == "Order update"
    assert "TRACK123" in (result.message or "")


def test_user_notification_handler_blocks_probation_results():
    handler = UserNotificationHandler()
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
    routing = OrderActionRoutingResult(action_intents=["user_notification"], diagnostics=[])

    result = handler.build_request(decision=decision, action_routing=routing, phase4=build_unresolved_phase4())

    assert result.queued is False
    assert result.blocked_reason == "decision:probation"


def test_user_notification_handler_builds_review_needed_message():
    handler = UserNotificationHandler()
    decision = OrderDecisionResult(
        decision="review_needed",
        decision_reason="no_structured_extraction",
        allow_persist_structured_result=True,
        allow_downstream_actions=True,
        requires_manual_review=True,
        confidence=0.0,
        confidence_level="low",
        extraction_source="active",
        profile_id="generic_order_confirmation",
        diagnostics=["decision:review_needed"],
    )
    routing = OrderActionRoutingResult(action_intents=["user_notification"], diagnostics=[])

    result = handler.build_request(decision=decision, action_routing=routing, phase4=build_unresolved_phase4())

    assert result.queued is True
    assert result.title == "Email review needed"
    assert "review" in (result.message or "").lower()
    assert (result.dedupe_key or "").startswith("email-user-notification:")
