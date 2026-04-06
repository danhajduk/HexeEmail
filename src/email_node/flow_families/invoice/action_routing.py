from __future__ import annotations

from email_node.shared_pipeline_core.actions import SharedActionRoutingPolicy
from email_node.shared_pipeline_core.family_yaml import (
    build_action_routing_policy_from_yaml,
    load_flow_family_yaml_definition,
)


def build_action_routing_policy() -> SharedActionRoutingPolicy:
    definition = load_flow_family_yaml_definition("invoice")
    return build_action_routing_policy_from_yaml(definition)


ACTION_ROUTING_POLICY = build_action_routing_policy()


__all__ = ["ACTION_ROUTING_POLICY", "build_action_routing_policy"]
