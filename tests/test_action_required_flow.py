from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from email_node.flow_families.action_required.runtime import GmailActionRequiredPhase3ProfileDetector
from email_node.patterns import ProbationStore, ProbationTemplateState
from email_node.pipeline import ActionRequiredFlowPipeline
from providers.gmail.models import GmailPhase1NormalizedEmail
from tests.test_gmail_order_phase3 import build_phase2_payload


def build_action_required_phase1_payload() -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="action-msg-1",
        thread_id="action-thread-1",
        provider_message_id="action-msg-1",
        provider_thread_id="action-thread-1",
        rfc_message_id="<action-msg-1@example.com>",
        subject="Action required: verify your account",
        sender_name="Security Team",
        sender_email="security@example.com",
        sender_domain="example.com",
        raw_sender="Security Team <security@example.com>",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=(
            "<html><body>"
            "<h1>Action required</h1>"
            "<p>Please verify your account before April 12.</p>"
            "<a href='https://example.com/verify'>Verify your account</a>"
            "</body></html>"
        ),
        selected_body_quality="rich_html",
        handoff_ready=True,
        validation_status="success",
    )


def build_site_issue_phase1_payload() -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="action-site-msg-1",
        thread_id="action-site-thread-1",
        provider_message_id="action-site-msg-1",
        provider_thread_id="action-site-thread-1",
        rfc_message_id="<action-site-msg-1@example.com>",
        subject="New reasons prevent pages from being indexed on site hexe-ai.com",
        sender_name="Google Search Console Team",
        sender_email="sc-noreply@google.com",
        sender_domain="google.com",
        raw_sender="Google Search Console Team <sc-noreply@google.com>",
        selected_body_type="text",
        selected_body_source="parsed_mime_text_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=(
            "New reasons prevent pages from being indexed on site hexe-ai.com.\n"
            "Open indexing report.\n"
            "Review the affected pages."
        ),
        selected_body_quality="usable_text",
        handoff_ready=True,
        validation_status="success",
    )


def test_action_required_flow_skeleton_runs_through_shared_core(tmp_path):
    result = asyncio.run(
        ActionRequiredFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_action_required_phase1_payload()
        )
    )

    assert result["flow_family"] == "action_required"
    assert result["phase2"].scrub_status in {"success", "partial", "failed"}
    assert result["phase3"].profile_status in {"success", "partial", "failed"}
    assert result["phase4"].extraction_status in {"unresolved", "failed"}
    assert result["phase6"].decision == "reject"
    assert result["phase7"].persisted is False


def test_action_required_detector_matches_payment_method_update():
    detector = GmailActionRequiredPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Your card's expiring soon--confirm your mailing address",
        sender_name="Capital One",
        sender_email="capitalone@notification.capitalone.com",
        sender_domain="notification.capitalone.com",
        scrubbed_text=(
            "Your card's expiring soon.\n"
            "Confirm your mailing address to get your replacement card.\n"
            "Sign in to your account."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "payment_method_update_required"
    assert result.profile_confidence_level in {"high", "medium"}


def test_action_required_detector_matches_application_completion():
    detector = GmailActionRequiredPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Rent is coming due soon: Complete your Flex profile to split your rent",
        sender_name="Flex",
        sender_email="team@payments.getflex.com",
        sender_domain="payments.getflex.com",
        scrubbed_text=(
            "Complete your Flex profile to split your rent.\n"
            "It looks like you created an account with Flex but didn't finish your application.\n"
            "See your new option."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "application_completion_required"
    assert result.profile_confidence_level in {"high", "medium"}


def test_action_required_detector_matches_site_issue():
    detector = GmailActionRequiredPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="New reasons prevent pages from being indexed on site hexe-ai.com",
        sender_name="Google Search Console Team",
        sender_email="sc-noreply@google.com",
        sender_domain="google.com",
        scrubbed_text=(
            "New reasons prevent pages from being indexed on site hexe-ai.com.\n"
            "Open indexing report.\n"
            "Review the affected pages."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "site_issue_action_required"
    assert result.profile_confidence_level in {"high", "medium"}


def test_action_required_phase4_builds_ai_template_hook_for_unresolved_result(tmp_path):
    result = asyncio.run(
        ActionRequiredFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_site_issue_phase1_payload()
        )
    )

    phase4 = result["phase4"]
    assert phase4.ai_template_hook is not None
    assert phase4.ai_template_hook["profile_id"] == "site_issue_action_required"
    assert phase4.ai_template_hook["profile_family"] == "action_required"
    assert phase4.ai_template_hook["scrubbed_text"]


def test_action_required_pipeline_loads_existing_probation_state(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation" / "templates",
        state_dir=tmp_path / "probation" / "state",
        evaluations_dir=tmp_path / "probation" / "evaluations",
        shadow_dir=tmp_path / "probation" / "shadow",
    )
    template_id = "example_account_verification_required.v1"
    store.save_template_payload(
        template_id,
        {
            "schema_version": "action-required-phase4-template.v1",
            "template_id": template_id,
            "profile_id": "site_issue_action_required",
            "template_version": "v1",
            "enabled": True,
            "match": {"vendor_identity": "google"},
            "extract": {},
            "required_fields": [],
            "confidence_rules": {"high_requires": []},
            "post_process": {},
        },
    )
    store.save_state(
        ProbationTemplateState(
            template_id=template_id,
            profile_id="site_issue_action_required",
            template_version="v1",
            created_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
        )
    )

    result = asyncio.run(
        ActionRequiredFlowPipeline(
            runtime_dir=tmp_path / "runtime",
            probation_store=store,
            ai_calls_enabled=lambda: True,
        ).process_normalized_email(build_site_issue_phase1_payload())
    )

    phase4 = result["phase4"]
    assert f"probation_template:existing:{template_id}" in phase4.template_diagnostics
    updated_state = store.load_state(template_id)
    assert updated_state is not None
    assert updated_state.sample_count == 2


def test_action_required_pipeline_creates_probation_template_for_unresolved_profile(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation" / "templates",
        state_dir=tmp_path / "probation" / "state",
        evaluations_dir=tmp_path / "probation" / "evaluations",
        shadow_dir=tmp_path / "probation" / "shadow",
    )
    seen = {}

    async def fake_generate(request):
        seen["request"] = request
        payload = {
            "schema_version": "action-required-phase4-template.v1",
            "template_id": request.template_id,
            "profile_id": request.profile_id,
            "template_version": request.template_version,
            "enabled": True,
            "match": {"vendor_identity": request.vendor_identity},
            "extract": {},
            "required_fields": [],
            "confidence_rules": {"high_requires": []},
            "post_process": {},
        }
        path = store.save_template_payload(request.template_id, payload)
        return {"ok": True, "template_id": request.template_id, "file_path": str(path)}

    pipeline = ActionRequiredFlowPipeline(
        runtime_dir=tmp_path / "runtime",
        probation_store=store,
        generate_probation_template=fake_generate,
        ai_calls_enabled=lambda: True,
    )
    phase2 = pipeline.phase2_scrubber.scrub(build_site_issue_phase1_payload())
    phase3 = pipeline.phase3_detector.detect(phase2)
    phase4 = pipeline.phase4_extractor.extract(phase3)

    result = asyncio.run(pipeline.runtime.attach_probation_template(phase4))

    assert seen["request"].expected_label == "ACTION_REQUIRED"
    assert seen["request"].profile_id == "site_issue_action_required"
    assert seen["request"].vendor_identity == "google"
    assert any(item.startswith("probation_template:created:") for item in result.template_diagnostics)
    state = store.find_state(
        profile_id="site_issue_action_required",
        vendor_identity="google",
        status="probation",
    )
    assert state is not None


def test_action_required_pipeline_applies_existing_probation_template_as_low_confidence_partial(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation" / "templates",
        state_dir=tmp_path / "probation" / "state",
        evaluations_dir=tmp_path / "probation" / "evaluations",
        shadow_dir=tmp_path / "probation" / "shadow",
    )
    template_id = "google_site_issue_action_required.v1"
    store.save_template_payload(
        template_id,
        {
            "schema_version": "action-required-phase4-template.v1",
            "template_id": template_id,
            "profile_id": "site_issue_action_required",
            "template_version": "v1",
            "enabled": True,
            "match": {"vendor_identity": "google"},
            "extract": {
                "issue_summary": {
                    "method": "line_contains",
                    "value": "prevent pages from being indexed",
                    "transforms": ["trim"],
                }
            },
            "required_fields": ["issue_summary"],
            "confidence_rules": {"high_requires": ["issue_summary"]},
            "post_process": {},
        },
    )
    store.save_state(
        ProbationTemplateState(
            template_id=template_id,
            profile_id="site_issue_action_required",
            template_version="v1",
            created_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
        )
    )

    result = asyncio.run(
        ActionRequiredFlowPipeline(
            runtime_dir=tmp_path / "runtime",
            probation_store=store,
            ai_calls_enabled=lambda: True,
        ).process_normalized_email(build_site_issue_phase1_payload())
    )

    phase4 = result["phase4"]
    phase6 = result["phase6"]
    assert phase4.template_id == template_id
    assert phase4.extraction_status == "partial"
    assert phase4.extraction_confidence_level == "low"
    assert phase4.extraction_confidence <= 0.49
    assert phase4.extracted_fields["issue_summary"].value.startswith("New reasons prevent pages")
    assert f"probation_template:applied:{template_id}" in phase4.template_diagnostics
    assert phase6.decision == "probation"
