from __future__ import annotations

from email_node.shared_pipeline_core.reporting import SharedFlowReportBuilder
from tests.test_order_probation_pipeline import build_phase2_payload, build_unresolved_phase4


def test_shared_report_builder_adds_flow_family_and_summary():
    builder = SharedFlowReportBuilder()
    normalized = build_phase2_payload().phase1_reference
    phase4 = build_unresolved_phase4().model_copy(
        update={
            "profile_id": "amazon_order_confirmation",
            "template_id": "amazon_order_confirmation.v1",
            "extraction_status": "success",
            "extraction_confidence": 0.95,
            "extraction_confidence_level": "high",
            "template_diagnostics": ["template_lookup:resolved:amazon_order_confirmation.v1"],
        }
    )
    flow_result = {
        "flow_family": "order",
        "flow_config": type("Config", (), {"output_schema_family": "order"})(),
        "phase2": build_phase2_payload(),
        "phase3": phase4.phase3_reference,
        "phase4": phase4,
        "phase6": {
            "decision": "accept",
            "decision_reason": "active_high_confidence",
        },
        "phase7": {
            "persisted": True,
            "trust_level": "trusted",
            "blocked_reason": None,
            "record_path": "runtime/order_outputs/trusted/demo.json",
            "diagnostics": ["phase7_persisted:trusted:demo-msg-1"],
        },
        "phase7_result": {"persisted_result": True},
        "action_gate": {"actions_allowed": True, "diagnostics": ["action_gate:allowed"]},
        "action_router": {"action_intents": ["store_order_record"], "diagnostics": ["action_router:intents:store_order_record"]},
        "order_record_write": {"queued": True},
        "user_notification": {"queued": True},
        "tracking_monitor": {"queued": False},
    }

    payload = builder.build_payload(
        ran_at="2026-04-06T08:00:00+00:00",
        label="amazon",
        account_id="primary",
        message_id="demo-msg-1",
        normalized=normalized,
        flow_result=flow_result,
    )

    assert payload["flow_family"] == "order"
    assert payload["report_summary"]["status"]["phase7"] == "persisted:trusted"
    assert payload["report_summary"]["actions"]["gate"]["actions_allowed"] is True


def test_shared_report_builder_markdown_keeps_order_report_shape():
    builder = SharedFlowReportBuilder()
    payload = {
        "ran_at": "2026-04-06T08:00:00+00:00",
        "label": "amazon",
        "account_id": "primary",
        "message_id": "demo-msg-1",
        "flow_family": "order",
        "output_schema_family": "order",
        "phase1": {"subject": "Ordered", "sender_email": "ship-confirm@amazon.com", "fetch_status": "success"},
        "phase2": {"scrub_status": "success"},
        "phase3": {
            "profile_status": "success",
            "profile_id": "amazon_order_confirmation",
            "profile_confidence": 0.85,
            "profile_confidence_level": "high",
        },
        "phase4": {
            "extraction_status": "success",
            "template_id": "amazon_order_confirmation.v1",
            "extraction_confidence": 0.95,
            "extraction_confidence_level": "high",
            "template_diagnostics": [],
        },
        "phase6": {"decision": "accept"},
        "phase7": {"persisted": True, "trust_level": "trusted", "blocked_reason": None, "record_path": "runtime/order_outputs/trusted/demo.json"},
        "action_gate": {"actions_allowed": True},
        "action_router": {"action_intents": ["store_order_record", "user_notification"]},
        "order_record_write": {"queued": True},
        "user_notification": {"queued": True},
        "tracking_monitor": {"queued": False},
    }

    markdown = builder.build_markdown(payload)

    assert "# ORDER Flow Report: demo-msg-1" in markdown
    assert "- Flow family: `order`" in markdown
    assert "## Status" in markdown
    assert "## Phase 7" in markdown
    assert "## Actions" in markdown


def test_shared_report_builder_renders_review_needed_phase7_status():
    builder = SharedFlowReportBuilder()

    payload = builder.build_payload(
        ran_at="2026-04-06T08:00:00+00:00",
        label="action_required",
        account_id="primary",
        message_id="demo-msg-review",
        normalized=build_phase2_payload().phase1_reference,
        flow_result={
            "flow_family": "action_required",
            "flow_config": type("Config", (), {"output_schema_family": "action_required"})(),
            "phase2": build_phase2_payload(),
            "phase3": build_unresolved_phase4().phase3_reference,
            "phase4": build_unresolved_phase4(),
            "phase6": {"decision": "review_needed", "decision_reason": "no_structured_extraction"},
            "phase7": {
                "persisted": True,
                "trust_level": "review_needed",
                "blocked_reason": None,
                "record_path": "runtime/flow_families/action_required/outputs/review_needed/demo-msg-review.json",
                "diagnostics": ["phase7_persisted:review_needed:demo-msg-review"],
            },
            "phase7_result": {"persisted_result": True},
            "action_gate": {"actions_allowed": True, "diagnostics": ["action_gate:allowed"]},
            "action_router": {
                "action_intents": ["user_notification", "mark_for_manual_review"],
                "diagnostics": ["action_router:intents:user_notification,mark_for_manual_review"],
            },
            "order_record_write": {"queued": False},
            "user_notification": {"queued": True},
            "tracking_monitor": {"queued": False},
        },
    )

    assert payload["report_summary"]["status"]["phase7"] == "persisted:review_needed"
    assert payload["report_summary"]["decision"]["decision"] == "review_needed"
