from __future__ import annotations

from email_node.shared_pipeline_core import get_flow_family_config, load_action_routing_policy


def test_action_routing_policy_loader_supports_order_and_action_required():
    order_policy = load_action_routing_policy(get_flow_family_config("order").action_router_policy)
    action_required_policy = load_action_routing_policy(get_flow_family_config("action_required").action_router_policy)

    assert order_policy.profile_intents["amazon_order_confirmation"] == ("store_order_record",)
    assert order_policy.decision_intents["accept"] == ("user_notification",)
    assert order_policy.decision_intents["review_needed"] == ("user_notification", "mark_for_manual_review")
    assert action_required_policy.decision_intents["accept"] == ("store_action_record", "user_notification")
    assert action_required_policy.decision_intents["review_needed"] == ("user_notification", "mark_for_manual_review")
    assert action_required_policy.diagnostic_token_intents["deadline"] == ("queue_reminder",)
