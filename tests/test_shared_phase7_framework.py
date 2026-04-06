from __future__ import annotations

from datetime import UTC, datetime

from email_node.shared_pipeline_core.actions import SharedActionGate, SharedActionRouter
from email_node.shared_pipeline_core.decision import SharedDecisionResult
from email_node.shared_pipeline_core.persistence import SharedOutputPersistenceHandler
from tests.test_order_probation_pipeline import build_unresolved_phase4


class DemoRouter(SharedActionRouter):
    def resolve_action_intents(self, *, decision, authorization, phase4):
        intents: list[str] = ["persist_record"]
        if getattr(phase4, "profile_id", None) == "demo_profile":
            intents.append("notify_user")
        return intents


def test_shared_action_gate_and_router_allow_active_accept_results():
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "demo_profile",
            "extracted_fields": {"order_number": {"value": "123"}},
        }
    )
    decision = SharedDecisionResult(
        decision="accept",
        decision_reason="active_high_confidence",
        allow_persist_structured_result=True,
        allow_downstream_actions=True,
        requires_manual_review=False,
        confidence=0.95,
        confidence_level="high",
        extraction_source="active",
        profile_id="demo_profile",
        diagnostics=["decision:accept"],
    )

    authorization = SharedActionGate().authorize(decision=decision, phase4=phase4)
    routing = DemoRouter().route(decision=decision, authorization=authorization, phase4=phase4)

    assert authorization.actions_allowed is True
    assert routing.action_intents == ["persist_record", "notify_user"]


def test_shared_persistence_handler_blocks_reject_results(tmp_path):
    phase4 = build_unresolved_phase4()
    decision = SharedDecisionResult(
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

    result = SharedOutputPersistenceHandler(flow_family="demo", runtime_dir=tmp_path / "runtime").persist(
        decision=decision,
        phase4=phase4,
    )

    assert result.persisted is False
    assert result.blocked_reason == "decision_blocked:no_structured_extraction"


def test_shared_persistence_handler_persists_partial_record(tmp_path):
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "demo_profile",
            "message_id": "demo-msg-1",
            "extracted_fields": {"order_number": {"value": "123"}},
            "received_at": datetime(2026, 4, 6, 7, 0, tzinfo=UTC),
        }
    )
    decision = SharedDecisionResult(
        decision="probation",
        decision_reason="active_medium_confidence",
        allow_persist_structured_result=True,
        allow_downstream_actions=False,
        requires_manual_review=True,
        confidence=0.64,
        confidence_level="medium",
        extraction_source="active",
        profile_id="demo_profile",
        diagnostics=["decision:probation"],
    )

    result = SharedOutputPersistenceHandler(flow_family="demo", runtime_dir=tmp_path / "runtime").persist(
        decision=decision,
        phase4=phase4,
    )

    assert result.persisted is True
    assert result.trust_level == "partial"
    assert result.record is not None
    assert result.record.flow_family == "demo"
    assert result.record.message_metadata["message_id"] == "demo-msg-1"
