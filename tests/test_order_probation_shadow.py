from __future__ import annotations

from datetime import UTC, datetime

from email_node.pipeline import OrderFlowPipeline
from email_node.patterns import ProbationStore, ProbationTemplateState
from providers.gmail.models import GmailPhase1Reference, GmailPhase2ScrubbedEmail
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


def build_active_phase2_payload() -> GmailPhase2ScrubbedEmail:
    phase2 = GmailPhase2ScrubbedEmail(
        phase1_reference=GmailPhase1Reference(
            schema_version="gmail.phase1.normalized.v1",
            provider="gmail",
            message_id="msg-order-1",
            thread_id="thread-1",
            provider_message_id="msg-order-1",
            provider_thread_id="thread-1",
            rfc_message_id="<msg-order-1@example.com>",
            subject='Ordered: "ESP32-S3-BOX-3B Development..."',
            sender_name="Amazon.com",
            sender_email="auto-confirm@amazon.com",
            sender_domain="amazon.com",
            selected_body_type="html",
            selected_body_source="parsed_mime_html_part",
            selected_body_selection_path="quality_comparison",
            handoff_ready=True,
            fetch_status="success",
            mime_parse_status="success",
            validation_status="success",
        ),
        message_id="msg-order-1",
        thread_id="thread-1",
        provider_message_id="msg-order-1",
        provider_thread_id="thread-1",
        rfc_message_id="<msg-order-1@example.com>",
        subject='Ordered: "ESP32-S3-BOX-3B Development..."',
        sender_name="Amazon.com",
        sender_email="auto-confirm@amazon.com",
        sender_domain="amazon.com",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        scrubbed_text=(
            "Thanks for your order, Slobodan!\n"
            "Ordered\n"
            "Arriving tomorrow\n"
            "Order # 112-0381957-4204214\n"
            "View or edit order\n"
            "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214\n"
            "Quantity: 1\n"
            "Grand Total:\n50 USD"
        ),
        normalized_lines=[
            "Thanks for your order, Slobodan!",
            "Ordered",
            "Arriving tomorrow",
            "Order # 112-0381957-4204214",
            "View or edit order",
            "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214",
            "Quantity: 1",
            "Grand Total:",
            "50 USD",
        ],
        scrub_status="success",
        transactional_quality="success",
    )
    phase2.extracted_links.append(
        {
            "label": "View or edit order",
            "url": "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214",
            "normalized_url": "https://www.amazon.com/your-orders/order-details?orderID=112-0381957-4204214",
            "link_type": "order_action",
            "source": "plain_text",
            "is_tracking": False,
            "is_valid": True,
            "diagnostics": [],
        }
    )
    return phase2


def test_order_pipeline_runs_probation_shadow_without_changing_active_result(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
        shadow_dir=tmp_path / "probation_shadow",
    )
    template_id = "amazon_order_confirmation_probation.v1"
    store.save_template_payload(
        template_id,
        {
            "schema_version": "order-phase4-template.v1",
            "template_id": template_id,
            "profile_id": "amazon_order_confirmation",
            "template_version": "v1",
            "enabled": True,
            "match": {"vendor_identity": "amazon"},
            "extract": {
                "order_number": {"method": "regex", "pattern": r"Order\s*#\s*([0-9-]{10,})"},
            },
            "required_fields": ["order_number"],
            "confidence_rules": {"high_requires": ["order_number"]},
            "post_process": {},
        },
    )
    store.save_state(
        ProbationTemplateState(
            template_id=template_id,
            profile_id="amazon_order_confirmation",
            template_version="v1",
            created_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
        )
    )

    pipeline = OrderFlowPipeline(probation_store=store, ai_calls_enabled=lambda: True)
    phase3 = pipeline.phase3_detector.detect(build_active_phase2_payload())
    active_phase4 = pipeline.phase4_extractor.extract(phase3)

    shadowed = pipeline._run_probation_shadow_mode(active_phase4)

    assert shadowed.template_id == "amazon_order_confirmation.v1"
    assert f"probation_template:shadow:{template_id}" in shadowed.template_diagnostics
    comparisons = store.list_shadow_comparisons(template_id)
    assert len(comparisons) == 1
    assert comparisons[0]["active_template_id"] == "amazon_order_confirmation.v1"
