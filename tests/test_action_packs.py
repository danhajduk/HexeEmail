from __future__ import annotations

from email_node.shared_pipeline_core import get_flow_family_config, load_action_routing_policy


def test_action_routing_policy_loader_supports_order_and_action_needed():
    order_policy = load_action_routing_policy(get_flow_family_config("order").action_router_policy)
    action_needed_policy = load_action_routing_policy(get_flow_family_config("action_needed").action_router_policy)

    assert order_policy.profile_intents["amazon_order_confirmation"] == ("store_order_record",)
    assert order_policy.decision_intents["accept"] == ("user_notification",)
    assert action_needed_policy.decision_intents["accept"] == ("store_action_record", "user_notification")
    assert action_needed_policy.diagnostic_token_intents["deadline"] == ("queue_reminder",)
