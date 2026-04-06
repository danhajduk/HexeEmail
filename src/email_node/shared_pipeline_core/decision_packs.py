from __future__ import annotations

import importlib

from email_node.shared_pipeline_core.decision import SharedDecisionPolicy


def load_decision_policy(pack_reference: str) -> SharedDecisionPolicy:
    module = importlib.import_module(pack_reference)
    builder = getattr(module, "build_decision_policy", None)
    if callable(builder):
        policy = builder()
        if isinstance(policy, SharedDecisionPolicy):
            return policy
    policy = getattr(module, "DECISION_POLICY", None)
    if isinstance(policy, SharedDecisionPolicy):
        return policy
    raise ValueError(f"Unsupported decision policy pack: {pack_reference}")
