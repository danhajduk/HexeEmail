from __future__ import annotations

import importlib

from email_node.shared_pipeline_core.validation import SharedValidationPolicy


def load_validation_policy(pack_reference: str) -> SharedValidationPolicy:
    module = importlib.import_module(pack_reference)
    builder = getattr(module, "build_validation_policy", None)
    if callable(builder):
        policy = builder()
        if isinstance(policy, SharedValidationPolicy):
            return policy
    policy = getattr(module, "VALIDATION_POLICY", None)
    if isinstance(policy, SharedValidationPolicy):
        return policy
    raise ValueError(f"Unsupported validation policy pack: {pack_reference}")
