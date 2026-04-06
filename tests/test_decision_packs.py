from __future__ import annotations

from email_node.shared_pipeline_core import get_flow_family_config, load_decision_policy


def test_decision_policy_loader_supports_order_and_action_required():
    order_policy = load_decision_policy(get_flow_family_config("order").decision_policy)
    action_required_policy = load_decision_policy(get_flow_family_config("action_required").decision_policy)

    assert order_policy.high_confidence_threshold == 0.85
    assert order_policy.medium_confidence_threshold == 0.60
    assert action_required_policy.high_confidence_threshold == 0.9
    assert action_required_policy.medium_confidence_threshold == 0.65
