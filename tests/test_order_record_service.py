from __future__ import annotations

import json
from pathlib import Path

from email_node.orders import OrderRecordService
from email_node.pipeline import OrderActionRoutingResult, OrderDecisionResult
from tests.test_order_probation_pipeline import build_unresolved_phase4


def test_order_record_service_creates_record_for_accept_result(tmp_path: Path):
    service = OrderRecordService(runtime_dir=tmp_path / "runtime")
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "reservation_confirmation",
            "extracted_fields": {
                "order_number": {"value": "0892885499"},
                "item_name": {"value": "Death Valley National Park Site Pass"},
                "total": {"value": "30.00 USD"},
                "status": {"value": "confirmed"},
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
        profile_id="reservation_confirmation",
        diagnostics=["decision:accept"],
    )
    routing = OrderActionRoutingResult(action_intents=["store_order_record"], diagnostics=["action_router:intents:store_order_record"])

    result = service.write_from_order_result(decision=decision, phase4=phase4, action_routing=routing)

    assert result.written is True
    assert result.operation == "created"
    payload = json.loads((tmp_path / "runtime" / "order_records" / "order:0892885499.json").read_text())
    assert payload["profile_id"] == "reservation_confirmation"
    assert payload["order_number"] == "0892885499"
    assert payload["item_titles"] == ["Death Valley National Park Site Pass"]


def test_order_record_service_updates_existing_record_by_order_number(tmp_path: Path):
    service = OrderRecordService(runtime_dir=tmp_path / "runtime")
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "message_id": "msg-2",
            "profile_id": "reservation_confirmation",
            "extracted_fields": {
                "order_number": {"value": "0892885499"},
                "item_name": {"value": "Updated Pass"},
                "status": {"value": "confirmed"},
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
        profile_id="reservation_confirmation",
        diagnostics=["decision:accept"],
    )
    routing = OrderActionRoutingResult(action_intents=["store_order_record"], diagnostics=[])

    first = service.write_from_order_result(decision=decision, phase4=phase4, action_routing=routing)
    second = service.write_from_order_result(decision=decision, phase4=phase4, action_routing=routing)

    assert first.operation == "created"
    assert second.operation == "updated"
    assert second.order_record_id == "order:0892885499"


def test_order_record_service_skips_probation_results(tmp_path: Path):
    service = OrderRecordService(runtime_dir=tmp_path / "runtime")
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
    routing = OrderActionRoutingResult(action_intents=["store_order_record"], diagnostics=[])

    result = service.write_from_order_result(decision=decision, phase4=build_unresolved_phase4(), action_routing=routing)

    assert result.written is False
    assert result.blocked_reason == "decision:probation"
