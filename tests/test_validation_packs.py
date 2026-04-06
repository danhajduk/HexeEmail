from __future__ import annotations

from email_node.shared_pipeline_core import get_flow_family_config, load_validation_policy


def test_validation_policy_loader_supports_order_and_action_required():
    order_policy = load_validation_policy(get_flow_family_config("order").validation_policy)
    action_required_policy = load_validation_policy(get_flow_family_config("action_required").validation_policy)

    assert order_policy.identifier_fields == ("order_number", "tracking_number")
    assert action_required_policy.identifier_fields == ("action_id", "document_id")
    assert action_required_policy.url_field_suffixes == ("_url", "_action")
