from __future__ import annotations

from email_node.shared_pipeline_core.actions import SharedActionRoutingPolicy


ACTION_ROUTING_POLICY = SharedActionRoutingPolicy(
    decision_intents={
        "accept": ("store_action_record", "user_notification"),
        "probation": ("mark_for_manual_review",),
    },
    diagnostic_token_intents={
        "important_inconsistency": ("mark_high_priority", "mark_for_manual_review"),
        "deadline": ("queue_reminder",),
    },
)


def build_action_routing_policy() -> SharedActionRoutingPolicy:
    return ACTION_ROUTING_POLICY
