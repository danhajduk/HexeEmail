from __future__ import annotations

from pathlib import Path

from email_node.shared_pipeline_core.profile_packs import SharedProfileDefinitionPack


PROFILE_TAXONOMY_VERSION = "action-needed-phase3-taxonomy.v1"


PROFILE_TAXONOMY: dict[str, dict[str, str | None]] = {
    "payment_due": {
        "profile_family": "action_needed",
        "profile_subtype": "payment_due",
        "vendor_identity": None,
    },
    "subscription_payment_failed": {
        "profile_family": "action_needed",
        "profile_subtype": "subscription_payment_failed",
        "vendor_identity": None,
    },
    "account_verification_required": {
        "profile_family": "action_needed",
        "profile_subtype": "account_verification_required",
        "vendor_identity": None,
    },
    "security_alert_action_required": {
        "profile_family": "action_needed",
        "profile_subtype": "security_alert_action_required",
        "vendor_identity": None,
    },
    "document_signature_required": {
        "profile_family": "action_needed",
        "profile_subtype": "document_signature_required",
        "vendor_identity": None,
    },
    "generic_action_required": {
        "profile_family": "action_needed",
        "profile_subtype": "generic_action_required",
        "vendor_identity": None,
    },
}


KNOWN_VENDOR_IDENTITIES: dict[str, str] = {}


DEFAULT_PHASE3_RULES: dict[str, object] = {
    "schema_version": "action-needed-phase3-rules.v1",
    "signals": {
        "payment_due_terms": ["payment due", "invoice due", "amount due", "past due"],
        "subscription_payment_failed_terms": ["payment failed", "subscription payment failed", "billing issue"],
        "account_verification_terms": ["verify your account", "confirm your account", "verification required"],
        "security_alert_terms": ["security alert", "suspicious login", "unusual sign-in"],
        "document_signature_terms": ["signature required", "sign document", "review and sign"],
        "generic_action_terms": ["action required", "requires your attention", "respond by"],
    },
    "sender_domain_profiles": {},
    "weights": {
        "sender_match": 5,
        "payment_due_language": 8,
        "subscription_payment_failed_language": 9,
        "account_verification_language": 9,
        "security_alert_language": 9,
        "document_signature_language": 8,
        "generic_action_language": 6,
    },
    "thresholds": {
        "high_score": 14,
        "medium_score": 8,
        "max_score": 20,
        "min_confidence": 0.05,
        "min_confidence_after_downgrade": 0.2,
    },
    "conflicts": {
        "pairs": [],
        "ignore_when_any_terms_present": [],
        "close_competing_score_gap": 2,
        "close_competing_confidence_penalty": 0.2,
        "conflicting_state_penalty": 0.15,
    },
}


def build_profile_definition_pack(*, runtime_dir: Path | None = None) -> SharedProfileDefinitionPack:
    base_runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
    return SharedProfileDefinitionPack(
        flow_family="action_needed",
        taxonomy_version=PROFILE_TAXONOMY_VERSION,
        taxonomy=PROFILE_TAXONOMY,
        known_vendor_identities=KNOWN_VENDOR_IDENTITIES,
        default_rules=DEFAULT_PHASE3_RULES,
        runtime_rules_path=base_runtime_dir / "flow_families" / "action_needed" / "profile_rules.json",
    )
