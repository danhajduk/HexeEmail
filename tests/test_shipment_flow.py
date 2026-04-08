from __future__ import annotations

import asyncio

from email_node.patterns import ProbationStore
from email_node.flow_families.shipment.runtime import GmailShipmentPhase3ProfileDetector
from email_node.pipeline.shipment_flow import ShipmentFlowPipeline
from providers.gmail.models import GmailPhase1NormalizedEmail
from tests.test_gmail_order_phase3 import build_phase2_payload


def build_shipment_phase1_payload() -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="shipment-msg-1",
        thread_id="shipment-thread-1",
        provider_message_id="shipment-msg-1",
        provider_thread_id="shipment-thread-1",
        rfc_message_id="<shipment-msg-1@example.com>",
        subject="Your package has shipped",
        sender_name="Example Shipping",
        sender_email="shipping@example.com",
        sender_domain="example.com",
        raw_sender="Example Shipping <shipping@example.com>",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=(
            "<html><body>"
            "<h1>Your package has shipped</h1>"
            "<p>Track your delivery for the latest update.</p>"
            "<a href='https://example.com/track'>Track package</a>"
            "</body></html>"
        ),
        selected_body_quality="rich_html",
        handoff_ready=True,
        validation_status="success",
    )


def test_shipment_flow_skeleton_runs_through_shared_core(tmp_path):
    result = asyncio.run(
        ShipmentFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_shipment_phase1_payload()
        )
    )

    assert result["flow_family"] == "shipment"
    assert result["phase2"].scrub_status in {"success", "partial", "failed"}
    assert result["phase3"].profile_id == "shipped"
    assert result["phase3"].profile_status in {"success", "partial"}
    assert result["phase4"].extraction_status == "unresolved"
    assert result["phase6"].decision == "review_needed"
    assert result["phase7"].persisted is True
    assert result["phase7"].trust_level == "review_needed"
    assert result["user_notification"].queued is True


def test_shipment_detector_matches_out_for_delivery():
    detector = GmailShipmentPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Your package is out for delivery",
        sender_name="UPS",
        sender_email="mcinfo@ups.com",
        sender_domain="ups.com",
        scrubbed_text=(
            "Your package is out for delivery today.\n"
            "Track your package for the latest update."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "out_for_delivery"
    assert result.profile_confidence_level in {"high", "medium"}


def test_shipment_detector_matches_delayed():
    detector = GmailShipmentPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Delivery delayed for your shipment",
        sender_name="FedEx",
        sender_email="tracking@fedex.com",
        sender_domain="fedex.com",
        scrubbed_text=(
            "Delivery delayed.\n"
            "Your shipment is running late due to an exception in transit."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "delayed"
    assert result.profile_confidence_level in {"high", "medium"}


def test_shipment_phase4_builds_ai_template_hook_for_unresolved_result(tmp_path):
    result = asyncio.run(
        ShipmentFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_shipment_phase1_payload()
        )
    )

    phase4 = result["phase4"]
    assert phase4.ai_template_hook is not None
    assert phase4.ai_template_hook["profile_id"] == "shipped"
    assert phase4.ai_template_hook["profile_family"] == "shipment"
    assert phase4.ai_template_hook["scrubbed_text"]


def test_shipment_pipeline_creates_probation_template_for_unresolved_profile(tmp_path):
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
                "schema_version": "shipment-phase4-template.v1",
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
        ShipmentFlowPipeline(
            runtime_dir=tmp_path / "runtime",
            probation_store=store,
            generate_probation_template=fake_generate,
            ai_calls_enabled=lambda: True,
        ).process_normalized_email(build_shipment_phase1_payload())
    )

    phase4 = result["phase4"]
    assert any(item.startswith("probation_template:created:") for item in phase4.template_diagnostics)
    assert seen["request"].expected_label == "SHIPMENT"
    state = store.load_state(seen["request"].template_id)
    assert state is not None
    assert state.profile_id == "shipped"
    assert state.last_generation_result == "created"
