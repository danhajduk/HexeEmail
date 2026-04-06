from __future__ import annotations

import asyncio

from email_node.flow_families.security.runtime import GmailSecurityPhase3ProfileDetector
from email_node.pipeline.security_flow import SecurityFlowPipeline
from providers.gmail.models import GmailPhase1NormalizedEmail
from tests.test_gmail_order_phase3 import build_phase2_payload


def build_security_phase1_payload() -> GmailPhase1NormalizedEmail:
    return GmailPhase1NormalizedEmail(
        message_id="security-msg-1",
        thread_id="security-thread-1",
        provider_message_id="security-msg-1",
        provider_thread_id="security-thread-1",
        rfc_message_id="<security-msg-1@example.com>",
        subject="Security alert for your account",
        sender_name="Example Security",
        sender_email="security@example.com",
        sender_domain="example.com",
        raw_sender="Example Security <security@example.com>",
        selected_body_type="html",
        selected_body_source="parsed_mime_html_part",
        selected_body_selection_path="quality_comparison",
        selected_body_content=(
            "<html><body>"
            "<h1>Security alert</h1>"
            "<p>Please review recent account activity.</p>"
            "<a href='https://example.com/security'>Secure account</a>"
            "</body></html>"
        ),
        selected_body_quality="rich_html",
        handoff_ready=True,
        validation_status="success",
    )


def test_security_flow_skeleton_runs_through_shared_core(tmp_path):
    result = asyncio.run(
        SecurityFlowPipeline(runtime_dir=tmp_path / "runtime").process_normalized_email(
            build_security_phase1_payload()
        )
    )

    assert result["flow_family"] == "security"
    assert result["phase2"].scrub_status in {"success", "partial", "failed"}
    assert result["phase3"].profile_id == "security_alert"
    assert result["phase3"].profile_status in {"success", "partial"}
    assert result["phase4"].extraction_status == "unresolved"
    assert result["phase6"].decision == "review_needed"
    assert result["phase7"].persisted is True
    assert result["phase7"].trust_level == "review_needed"
    assert result["user_notification"].queued is True


def test_security_detector_matches_suspicious_login():
    detector = GmailSecurityPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Suspicious login detected",
        sender_name="Google Security",
        sender_email="no-reply@google.com",
        sender_domain="google.com",
        scrubbed_text=(
            "Suspicious login detected.\n"
            "Review this unusual sign-in to protect your account."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "suspicious_login"
    assert result.profile_confidence_level in {"high", "medium"}


def test_security_detector_matches_mfa_code():
    detector = GmailSecurityPhase3ProfileDetector()
    phase2 = build_phase2_payload(
        subject="Your verification code",
        sender_name="Microsoft Account",
        sender_email="account-security-noreply@microsoft.com",
        sender_domain="microsoft.com",
        scrubbed_text=(
            "Your verification code is 472811.\n"
            "Use this code to complete sign in."
        ),
    )

    result = detector.detect(phase2)

    assert result.profile_id == "mfa_code"
    assert result.profile_confidence_level in {"high", "medium"}
