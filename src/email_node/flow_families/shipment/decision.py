from __future__ import annotations

from email_node.shared_pipeline_core.decision import SharedDecisionPolicy
from email_node.shared_pipeline_core.family_yaml import (
    build_decision_policy_from_yaml,
    load_flow_family_yaml_definition,
)


def build_decision_policy() -> SharedDecisionPolicy:
    definition = load_flow_family_yaml_definition("shipment")
    return build_decision_policy_from_yaml(definition)


DECISION_POLICY = build_decision_policy()


__all__ = ["DECISION_POLICY", "build_decision_policy"]
