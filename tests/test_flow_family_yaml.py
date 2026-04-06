from __future__ import annotations

from pathlib import Path

import pytest

from email_node.shared_pipeline_core.family_yaml import (
    FlowFamilyYamlDefinition,
    build_action_routing_policy_from_yaml,
    build_flow_family_config_from_yaml,
    build_decision_policy_from_yaml,
    build_profile_definition_pack_from_yaml,
    build_scrub_heuristic_pack_from_yaml,
    build_validation_policy_from_yaml,
    load_flow_family_yaml_definition,
)
from email_node.shared_pipeline_core.families import get_flow_family_config
from email_node.shared_pipeline_core.profile_packs import load_profile_definition_pack


FAMILY_YAML = """
schema_version: flow-family-config.v1
flow_family: order
output_schema_family: order
runtime_paths:
  template_dir: flow_families/order/templates
  probation_template_dir: flow_families/order/probation/templates
  probation_state_dir: flow_families/order/probation/state
  probation_evaluations_dir: flow_families/order/probation/evaluations
  probation_shadow_dir: flow_families/order/probation/shadow
  output_dir: flow_families/order/outputs
  reports_dir: order_flow_logs/ad_hoc_reports
heuristics:
  ignore_line_patterns: ["^\\\\s*unsubscribe\\\\s*$"]
  stop_marker_patterns: ["^\\\\s*privacy notice\\\\s*$"]
  chrome_line_patterns: ["^\\\\s*your orders\\\\s*$"]
  footer_cutoff_patterns: ["copyright\\\\s+\\\\d{4}"]
  important_link_patterns:
    order_action: "order|purchase"
  tracking_host_patterns: ["/track|/pixel"]
  filler_entity_patterns: ["(?:&nbsp;){3,}"]
  transactional_anchor_patterns: ["thanks for your order"]
  promo_marker_patterns: ["recommended for you"]
profiles:
  taxonomy_version: order-phase3-taxonomy.v2
  taxonomy:
    generic_order_confirmation:
      profile_family: order
      profile_subtype: confirmation
      vendor_identity:
  known_vendor_identities:
    example.com: example_vendor
  rules_override_path: order_profile_rules.json
  rules:
    schema_version: order-phase3-rules.v1
    signals:
      confirmation_terms: ["order confirmation"]
    sender_domain_profiles:
      example.com: generic_order_confirmation
    weights:
      sender_match: 5
      confirmation_subject: 4
    thresholds:
      high_score: 14
      medium_score: 8
      max_score: 20
      min_confidence: 0.05
      min_confidence_after_downgrade: 0.2
    conflicts:
      pairs: []
      ignore_when_any_terms_present: []
      close_competing_score_gap: 2
      close_competing_confidence_penalty: 0.2
      conflicting_state_penalty: 0.15
validation_policy:
  url_field_suffixes: ["_url"]
  identifier_fields: ["order_number"]
  identifier_min_length: 6
  success_threshold: 0.85
  partial_threshold: 0.5
  required_field_confidence_weight: 0.6
  valid_field_confidence_weight: 0.4
decision_policy:
  high_confidence_threshold: 0.85
  medium_confidence_threshold: 0.6
action_routing_policy:
  profile_intents:
    generic_order_confirmation: ["store_order_record"]
  decision_intents:
    accept: ["user_notification"]
  diagnostic_token_intents:
    important_inconsistency: ["mark_for_manual_review"]
  field_rules:
    - required_fields: ["tracking_number"]
      any_of_fields: ["carrier", "order_number"]
      intents: ["attach_tracking_reference"]
"""


def test_flow_family_yaml_loader_reads_runtime_yaml(tmp_path):
    family_path = tmp_path / "flow_families" / "order" / "family.yaml"
    family_path.parent.mkdir(parents=True, exist_ok=True)
    family_path.write_text(FAMILY_YAML, encoding="utf-8")

    definition = load_flow_family_yaml_definition("order", runtime_dir=tmp_path)

    assert definition.flow_family == "order"
    assert definition.runtime_paths.template_dir == "flow_families/order/templates"
    assert definition.profiles.taxonomy["generic_order_confirmation"].profile_subtype == "confirmation"

    scrub_pack = build_scrub_heuristic_pack_from_yaml(definition)
    profile_pack = build_profile_definition_pack_from_yaml(definition, runtime_dir=tmp_path)
    validation_policy = build_validation_policy_from_yaml(definition)
    decision_policy = build_decision_policy_from_yaml(definition)
    action_policy = build_action_routing_policy_from_yaml(definition)
    flow_config = build_flow_family_config_from_yaml(definition, runtime_dir=tmp_path)

    assert scrub_pack.important_link_patterns["order_action"].pattern == "order|purchase"
    assert profile_pack.load_rules()["sender_domain_profiles"]["example.com"] == "generic_order_confirmation"
    assert validation_policy.identifier_fields == ("order_number",)
    assert decision_policy.high_confidence_threshold == 0.85
    assert action_policy.profile_intents["generic_order_confirmation"] == ("store_order_record",)
    assert flow_config.template_dir == tmp_path / "flow_families" / "order" / "templates"
    assert flow_config.scrub_heuristic_pack == "yaml://order"


def test_get_flow_family_config_prefers_yaml_when_present(tmp_path):
    family_path = tmp_path / "flow_families" / "order" / "family.yaml"
    family_path.parent.mkdir(parents=True, exist_ok=True)
    family_path.write_text(FAMILY_YAML, encoding="utf-8")

    config = get_flow_family_config("order", runtime_dir=tmp_path)

    assert config.scrub_heuristic_pack == "yaml://order"
    assert config.profile_detector_pack == "yaml://order"
    assert config.template_dir == tmp_path / "flow_families" / "order" / "templates"
    assert config.probation_state_dir == tmp_path / "flow_families" / "order" / "probation" / "state"


def test_shared_pack_loader_falls_back_to_python_module_reference():
    profile_pack = load_profile_definition_pack("email_node.flow_families.action_required.profiles")

    assert profile_pack.flow_family == "action_required"
    assert "generic_action_required" in profile_pack.taxonomy


def test_repo_yaml_definitions_load_for_both_families():
    order_definition = load_flow_family_yaml_definition("order")
    action_required_definition = load_flow_family_yaml_definition("action_required")

    assert order_definition.flow_family == "order"
    assert action_required_definition.flow_family == "action_required"
    assert order_definition.profiles.rules_override_path == "order_profile_rules.json"
    assert action_required_definition.runtime_paths.template_dir == "flow_families/action_required/templates"


def test_flow_family_yaml_definition_rejects_unknown_keys():
    with pytest.raises(Exception):
        FlowFamilyYamlDefinition.model_validate(
            {
                "schema_version": "flow-family-config.v1",
                "flow_family": "order",
                "output_schema_family": "order",
                "runtime_paths": {
                    "template_dir": "flow_families/order/templates",
                    "probation_template_dir": "flow_families/order/probation/templates",
                    "probation_state_dir": "flow_families/order/probation/state",
                    "probation_evaluations_dir": "flow_families/order/probation/evaluations",
                    "probation_shadow_dir": "flow_families/order/probation/shadow",
                    "output_dir": "flow_families/order/outputs",
                },
                "heuristics": {
                    "ignore_line_patterns": [],
                    "stop_marker_patterns": [],
                    "chrome_line_patterns": [],
                    "footer_cutoff_patterns": [],
                    "important_link_patterns": {},
                    "tracking_host_patterns": [],
                    "filler_entity_patterns": [],
                    "transactional_anchor_patterns": [],
                    "promo_marker_patterns": [],
                    "unexpected_key": True,
                },
                "profiles": {
                    "taxonomy_version": "v1",
                    "taxonomy": {},
                    "known_vendor_identities": {},
                    "rules": {
                        "schema_version": "v1",
                        "signals": {},
                        "sender_domain_profiles": {},
                        "weights": {},
                        "thresholds": {},
                        "conflicts": {
                            "pairs": [],
                            "ignore_when_any_terms_present": [],
                            "close_competing_score_gap": 2,
                            "close_competing_confidence_penalty": 0.2,
                            "conflicting_state_penalty": 0.15,
                        },
                    },
                },
                "validation_policy": {
                    "url_field_suffixes": [],
                    "identifier_fields": [],
                    "identifier_min_length": 1,
                    "success_threshold": 0.85,
                    "partial_threshold": 0.5,
                    "required_field_confidence_weight": 0.6,
                    "valid_field_confidence_weight": 0.4,
                },
                "decision_policy": {
                    "high_confidence_threshold": 0.85,
                    "medium_confidence_threshold": 0.6,
                },
                "action_routing_policy": {
                    "profile_intents": {},
                    "decision_intents": {},
                    "diagnostic_token_intents": {},
                    "field_rules": [],
                },
            }
        )
