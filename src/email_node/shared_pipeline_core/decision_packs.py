from __future__ import annotations

import importlib

from email_node.shared_pipeline_core.decision import SharedDecisionPolicy


def load_decision_policy(pack_reference: str) -> SharedDecisionPolicy:
    from email_node.shared_pipeline_core.family_yaml import (
        build_decision_policy_from_yaml,
        is_yaml_family_reference,
        load_flow_family_yaml_definition,
        parse_yaml_family_reference,
    )

    if is_yaml_family_reference(pack_reference):
        flow_family = parse_yaml_family_reference(pack_reference)
        definition = load_flow_family_yaml_definition(flow_family)
        return build_decision_policy_from_yaml(definition)
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
