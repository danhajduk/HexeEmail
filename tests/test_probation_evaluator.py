from __future__ import annotations

from datetime import UTC, datetime

from email_node.patterns import ProbationEvaluator, ProbationStore, ProbationTemplateState
from providers.gmail.models import GmailPhase1Reference, GmailPhase2ScrubbedEmail
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector


def build_phase3():
    phase2 = GmailPhase2ScrubbedEmail(
        phase1_reference=GmailPhase1Reference(
            schema_version="gmail.phase1.normalized.v1",
            provider="gmail",
            message_id="phase2-msg-1",
            thread_id="phase2-thread-1",
            provider_message_id="phase2-msg-1",
            provider_thread_id="phase2-thread-1",
            rfc_message_id="<phase2-msg-1@example.com>",
            subject="Order Receipt",
            sender_name="Recreation.gov",
            sender_email="communications@recreation.gov",
            sender_domain="recreation.gov",
            selected_body_type="html",
            selected_body_source="parsed_mime_html_part",
            selected_body_selection_path="quality_comparison",
            handoff_ready=True,
            fetch_status="success",
            mime_parse_status="success",
            validation_status="success",
        ),
        message_id="phase2-msg-1",
        thread_id="phase2-thread-1",
        provider_message_id="phase2-msg-1",
        provider_thread_id="phase2-thread-1",
        rfc_message_id="<phase2-msg-1@example.com>",
        subject="Order Receipt",
        sender_name="Recreation.gov",
        sender_email="communications@recreation.gov",
        sender_domain="recreation.gov",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        scrubbed_text=(
            "Order Receipt\n"
            "Transaction Details\n"
            "0892885499\n"
            "Quantity: 1 Pass(es)\n"
            "Total:\n"
            "$30.00\n"
        ),
        normalized_lines=[
            "Order Receipt",
            "Transaction Details",
            "0892885499",
            "Quantity: 1 Pass(es)",
            "Total:",
            "$30.00",
        ],
        scrub_status="partial",
        transactional_quality="partial",
    )
    return GmailOrderPhase3ProfileDetector().detect(phase2)


def test_probation_evaluator_persists_deterministic_evaluation(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
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
                "order_number": {"method": "regex", "pattern": r"(?m)^([0-9]{10})$"},
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

    result = ProbationEvaluator(probation_store=store).evaluate(build_phase3(), template_id=template_id)

    assert result.matched is True
    assert result.required_fields_present is True
    assert result.high_requires_present is True
    assert result.extracted_fields["order_number"] == "0892885499"
    assert store.list_evaluations(template_id)[0]["message_id"] == "phase2-msg-1"
