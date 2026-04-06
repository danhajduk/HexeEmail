from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from email_node.pipeline import OrderFlowPipeline
from email_node.patterns import ProbationStore, ProbationTemplateState
from providers.gmail.models import GmailPhase1Reference, GmailPhase2ScrubbedEmail
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


def build_phase2_payload() -> GmailPhase2ScrubbedEmail:
    return GmailPhase2ScrubbedEmail(
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
            "Order Number:\n"
            "Please review the order details below.\n"
            "Transaction Details\n"
            "0892885499\n"
            "Quantity: 1 Pass(es)\n"
            "Total:\n"
            "$30.00\n"
        ),
        normalized_lines=[
            "Order Receipt",
            "Order Number:",
            "Please review the order details below.",
            "Transaction Details",
            "0892885499",
            "Quantity: 1 Pass(es)",
            "Total:",
            "$30.00",
        ],
        scrub_status="partial",
        transactional_quality="partial",
    )


def build_unresolved_phase4():
    phase3 = GmailOrderPhase3ProfileDetector().detect(build_phase2_payload())
    return GmailOrderPhase4Extractor().extract(phase3)


@pytest.mark.asyncio
async def test_order_pipeline_creates_probation_template_for_unresolved_profile(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
    )
    seen = {}

    async def fake_generate(request):
        seen["request"] = request
        payload = {
            "schema_version": "order-phase4-template.v1",
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

    pipeline = OrderFlowPipeline(
        probation_store=store,
        generate_probation_template=fake_generate,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
    )

    result = await pipeline.attach_probation_template(build_unresolved_phase4())

    assert seen["request"].profile_id == "reservation_confirmation"
    assert seen["request"].vendor_identity == "recreation_gov"
    assert any(item.startswith("probation_template:created:") for item in result.template_diagnostics)
    state = store.find_state(
        profile_id="reservation_confirmation",
        vendor_identity="recreation_gov",
        status="probation",
    )
    assert state is not None
    assert state.sample_count == 1


@pytest.mark.asyncio
async def test_order_pipeline_reuses_existing_probation_template_without_regenerating(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
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
            "extract": {},
            "required_fields": [],
            "confidence_rules": {"high_requires": []},
            "post_process": {},
        },
    )
    store.save_state(
        store.load_state(template_id)
        or ProbationTemplateState(
            template_id=template_id,
            profile_id="reservation_confirmation",
            template_version="v1",
            created_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
        )
    )
    generate_calls = 0

    async def should_not_run(request):
        nonlocal generate_calls
        generate_calls += 1
        return {}

    pipeline = OrderFlowPipeline(
        probation_store=store,
        generate_probation_template=should_not_run,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
    )

    result = await pipeline.attach_probation_template(build_unresolved_phase4())

    assert generate_calls == 0
    assert f"probation_template:existing:{template_id}" in result.template_diagnostics
    assert any(item.startswith(f"probation_template:evaluated:{template_id}:") for item in result.template_diagnostics)
    updated_state = store.load_state(template_id)
    assert updated_state is not None
    assert updated_state.sample_count == 2


@pytest.mark.asyncio
async def test_order_pipeline_applies_existing_probation_template_as_low_confidence_partial(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
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
                "order_number": {
                    "method": "line_after",
                    "marker": "transaction details",
                    "transforms": ["trim", "normalize_order_number"],
                },
                "total": {
                    "method": "line_after",
                    "marker": "total:",
                    "transforms": ["trim", "normalize_currency"],
                },
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

    pipeline = OrderFlowPipeline(
        probation_store=store,
        generate_probation_template=None,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
    )

    result = await pipeline.attach_probation_template(build_unresolved_phase4())

    assert result.template_id == template_id
    assert result.extraction_status == "partial"
    assert result.extraction_confidence_level == "low"
    assert result.extraction_confidence <= 0.49
    assert result.extracted_fields["order_number"].value == "0892885499"
    assert result.extracted_fields["total"].value == "$30.00"
    assert f"probation_template:existing:{template_id}" in result.template_diagnostics
    assert f"probation_template:applied:{template_id}" in result.template_diagnostics


@pytest.mark.asyncio
async def test_order_pipeline_skips_when_order_checks_are_disabled(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
    )
    generate_calls = 0

    async def should_not_run(request):
        nonlocal generate_calls
        generate_calls += 1
        return {}

    pipeline = OrderFlowPipeline(
        probation_store=store,
        generate_probation_template=should_not_run,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: False,
    )

    result = await pipeline.attach_probation_template(build_unresolved_phase4())

    assert generate_calls == 0
    assert "order_checks:disabled" in result.template_diagnostics


@pytest.mark.asyncio
async def test_order_pipeline_returns_phase6_decision_for_probation_result(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
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
                "order_number": {
                    "method": "line_after",
                    "marker": "transaction details",
                    "transforms": ["trim", "normalize_order_number"],
                },
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

    class StubPhase2Scrubber:
        def scrub(self, _normalized):
            return build_phase2_payload()

    pipeline = OrderFlowPipeline(
        phase2_scrubber=StubPhase2Scrubber(),
        probation_store=store,
        generate_probation_template=None,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
    )

    result = await pipeline.process_normalized_email(object())

    assert result["phase4"].template_id == template_id
    assert result["phase6"].decision == "probation"
    assert result["phase6"].extraction_source == "probation"
    assert result["phase6"].allow_downstream_actions is False
    assert result["phase7"].persisted is True
    assert result["phase7"].trust_level == "partial"
    assert result["action_gate"].actions_allowed is False
    assert result["action_gate"].blocked_reason == "decision_probation"
    assert result["action_router"].action_intents == []
    assert result["order_record_write"].written is False
    assert result["order_record_write"].blocked_reason == "decision:probation"
    assert result["user_notification"].queued is False
    assert result["user_notification"].blocked_reason == "decision:probation"
    state = store.load_state(template_id)
    assert state is not None
    assert state.status == "probation"
