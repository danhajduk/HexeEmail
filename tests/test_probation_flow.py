from __future__ import annotations

from datetime import UTC, datetime

import pytest

from email_node.pipeline import OrderFlowPipeline
from email_node.patterns import (
    ProbationPromotionManager,
    ProbationPromotionPolicy,
    ProbationStore,
    TemplatePromotionService,
)
from providers.gmail.models import GmailPhase1Reference, GmailPhase2ScrubbedEmail
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


def build_unresolved_phase4():
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
    phase3 = GmailOrderPhase3ProfileDetector().detect(phase2)
    return GmailOrderPhase4Extractor().extract(phase3)


@pytest.mark.asyncio
async def test_probation_flow_creates_evaluates_and_promotes_template(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
        shadow_dir=tmp_path / "probation_shadow",
    )
    active_dir = tmp_path / "active"

    async def fake_generate(request):
        path = store.save_template_payload(
            request.template_id,
            {
                "schema_version": "order-phase4-template.v1",
                "template_id": request.template_id,
                "profile_id": request.profile_id,
                "template_version": request.template_version,
                "enabled": True,
                "match": {"vendor_identity": request.vendor_identity},
                "extract": {
                    "order_number": {"method": "regex", "pattern": r"(?m)^([0-9]{10})$"},
                },
                "required_fields": ["order_number"],
                "confidence_rules": {"high_requires": ["order_number"]},
                "post_process": {},
            },
        )
        return {"ok": True, "template_id": request.template_id, "file_path": str(path)}

    pipeline = OrderFlowPipeline(
        probation_store=store,
        probation_promotion=ProbationPromotionManager(
            promotion_service=TemplatePromotionService(probation_store=store, active_dir=active_dir),
            policy=ProbationPromotionPolicy(minimum_sample_count=3),
        ),
        generate_probation_template=fake_generate,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
    )

    phase4 = build_unresolved_phase4()
    first = await pipeline.attach_probation_template(phase4)
    second = await pipeline.attach_probation_template(phase4)
    third = await pipeline.attach_probation_template(phase4)

    assert any(item.startswith("probation_template:created:") for item in first.template_diagnostics)
    assert any(item.startswith("probation_template:evaluated:") for item in second.template_diagnostics)
    assert any(item.endswith(":active") for item in third.template_diagnostics)
    state = store.find_state(profile_id="reservation_confirmation", vendor_identity="recreation_gov")
    assert state is not None
    assert state.status == "active"
    assert (active_dir / f"{state.template_id}.json").exists()


@pytest.mark.asyncio
async def test_probation_flow_keeps_failed_template_on_probation(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
        shadow_dir=tmp_path / "probation_shadow",
    )

    async def fake_generate(request):
        path = store.save_template_payload(
            request.template_id,
            {
                "schema_version": "order-phase4-template.v1",
                "template_id": request.template_id,
                "profile_id": request.profile_id,
                "template_version": request.template_version,
                "enabled": True,
                "match": {"vendor_identity": request.vendor_identity},
                "extract": {},
                "required_fields": ["order_number"],
                "confidence_rules": {"high_requires": ["order_number"]},
                "post_process": {},
            },
        )
        return {"ok": True, "template_id": request.template_id, "file_path": str(path)}

    pipeline = OrderFlowPipeline(
        probation_store=store,
        probation_promotion=ProbationPromotionManager(
            promotion_service=TemplatePromotionService(probation_store=store, active_dir=tmp_path / "active"),
            policy=ProbationPromotionPolicy(minimum_sample_count=3),
        ),
        generate_probation_template=fake_generate,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
    )

    phase4 = build_unresolved_phase4()
    await pipeline.attach_probation_template(phase4)
    await pipeline.attach_probation_template(phase4)
    result = await pipeline.attach_probation_template(phase4)

    state = store.find_state(profile_id="reservation_confirmation", vendor_identity="recreation_gov")
    assert state is not None
    assert state.status == "probation"
    assert "Needs refinement before promotion." == state.promotion_reason
    assert any("probation_template:state:" in item for item in result.template_diagnostics)
