from __future__ import annotations

import importlib

from email_node.shared_pipeline_core.actions import SharedActionRoutingPolicy


def load_action_routing_policy(pack_reference: str) -> SharedActionRoutingPolicy:
    module = importlib.import_module(pack_reference)
    builder = getattr(module, "build_action_routing_policy", None)
    if callable(builder):
        policy = builder()
        if isinstance(policy, SharedActionRoutingPolicy):
            return policy
    policy = getattr(module, "ACTION_ROUTING_POLICY", None)
    if isinstance(policy, SharedActionRoutingPolicy):
        return policy
    raise ValueError(f"Unsupported action routing policy pack: {pack_reference}")
