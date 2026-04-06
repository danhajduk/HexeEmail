from __future__ import annotations

from email_node.shared_pipeline_core.actions import SharedActionFieldRule, SharedActionRoutingPolicy


ACTION_ROUTING_POLICY = SharedActionRoutingPolicy(
    profile_intents={
        "reservation_confirmation": ("store_order_record",),
        "amazon_order_confirmation": ("store_order_record",),
        "generic_order_confirmation": ("store_order_record",),
        "amazon_order_status_update": ("update_order_record",),
        "generic_order_status_update": ("update_order_record",),
    },
    decision_intents={
        "accept": ("user_notification",),
    },
    diagnostic_token_intents={
        "important_inconsistency": ("mark_for_manual_review",),
    },
    field_rules=(
        SharedActionFieldRule(
            required_fields=("tracking_number",),
            any_of_fields=("carrier", "order_number"),
            intents=("attach_tracking_reference", "queue_tracking_monitor"),
        ),
    ),
)


def build_action_routing_policy() -> SharedActionRoutingPolicy:
    return ACTION_ROUTING_POLICY
