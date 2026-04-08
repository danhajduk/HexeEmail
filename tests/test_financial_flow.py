from __future__ import annotations

import asyncio

from email_node.patterns import ProbationStore
from email_node.flow_families.financial.runtime import GmailFinancialPhase3ProfileDetector
from email_node.pipeline.financial_flow import FinancialFlowPipeline
from providers.gmail.models import GmailPhase1NormalizedEmail
from tests.test_gmail_order_phase3 import build_phase2_payload


def build_financial_phase1_payload() -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="financial-msg-1",
        thread_id="financial-thread-1",
        provider_message_id="financial-msg-1",
        provider_thread_id="financial-thread-1",
        rfc_message_id="<financial-msg-1@example.com>",
        subject="Your monthly statement is ready",
        sender_name="Example Bank",
        sender_email="statements@examplebank.com",
        sender_domain="examplebank.com",
        raw_sender="Example Bank <statements@examplebank.com>",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=(
            "<html><body>"
            "<h1>Your monthly statement is ready</h1>"
            "<p>Review your latest account activity.</p>"
            "<a href='https://examplebank.com/statements'>View statement</a>"
            "</body></html>"
        ),
        selected_body_quality="rich_html",
        handoff_ready=True,
        validation_status="success",
    )


def test_financial_flow_skeleton_runs_through_shared_core(tmp_path):
    result = asyncio.run(
        FinancialFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_financial_phase1_payload()
        )
    )

    assert result["flow_family"] == "financial"
    assert result["phase2"].scrub_status in {"success", "partial", "failed"}
    assert result["phase3"].profile_id == "statement_ready"
    assert result["phase3"].profile_status in {"success", "partial"}
    assert result["phase4"].extraction_status == "unresolved"
    assert result["phase6"].decision == "review_needed"
    assert result["phase7"].persisted is True
    assert result["phase7"].trust_level == "review_needed"
    assert result["user_notification"].queued is True


def test_financial_detector_matches_payment_due():
    detector = GmailFinancialPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Your minimum payment due reminder",
        sender_name="Example Bank",
        sender_email="billing@examplebank.com",
        sender_domain="examplebank.com",
        scrubbed_text=(
            "Your minimum payment due is $125.00.\n"
            "Pay now to avoid a late fee.\n"
            "Due date: April 18."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "payment_due"
    assert result.profile_confidence_level in {"high", "medium"}


def test_financial_detector_matches_refund_processed():
    detector = GmailFinancialPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Your refund has been processed",
        sender_name="PayPal",
        sender_email="service@paypal.com",
        sender_domain="paypal.com",
        scrubbed_text=(
            "Your refund processed successfully.\n"
            "The refunded amount will appear on your account shortly."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "refund_processed"
    assert result.profile_confidence_level in {"high", "medium"}


def test_financial_phase4_builds_ai_template_hook_for_unresolved_result(tmp_path):
    result = asyncio.run(
        FinancialFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_financial_phase1_payload()
        )
    )

    phase4 = result["phase4"]
    assert phase4.ai_template_hook is not None
    assert phase4.ai_template_hook["profile_id"] == "statement_ready"
    assert phase4.ai_template_hook["profile_family"] == "financial"
    assert phase4.ai_template_hook["scrubbed_text"]


def test_financial_pipeline_creates_probation_template_for_unresolved_profile(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation" / "templates",
        state_dir=tmp_path / "probation" / "state",
        evaluations_dir=tmp_path / "probation" / "evaluations",
        shadow_dir=tmp_path / "probation" / "shadow",
    )
    seen = {}

    async def fake_generate(request):
        seen["request"] = request
        path = store.save_template_payload(
            request.template_id,
            {
                "schema_version": "financial-phase4-template.v1",
                "template_id": request.template_id,
                "profile_id": request.profile_id,
                "template_version": request.template_version,
                "enabled": True,
                "match": {"vendor_identity": request.vendor_identity},
                "extract": {},
                "required_fields": [],
                "confidence_rules": {"high_requires": []},
                "post_process": {},
            },
        )
        return {"ok": True, "template_id": request.template_id, "file_path": str(path)}

    result = asyncio.run(
        FinancialFlowPipeline(
            runtime_dir=tmp_path / "runtime",
            probation_store=store,
            generate_probation_template=fake_generate,
            ai_calls_enabled=lambda: True,
        ).process_normalized_email(build_financial_phase1_payload())
    )

    phase4 = result["phase4"]
    assert any(item.startswith("probation_template:created:") for item in phase4.template_diagnostics)
    assert seen["request"].expected_label == "FINANCIAL"
    state = store.load_state(seen["request"].template_id)
    assert state is not None
    assert state.profile_id == "statement_ready"
    assert state.last_generation_result == "created"
