from __future__ import annotations

from email_node.shared_pipeline_core.family_yaml import (
    build_validation_policy_from_yaml,
    load_flow_family_yaml_definition,
)
from email_node.shared_pipeline_core.validation import SharedValidationPolicy


def build_validation_policy() -> SharedValidationPolicy:
    definition = load_flow_family_yaml_definition("security")
    return build_validation_policy_from_yaml(definition)


VALIDATION_POLICY = build_validation_policy()


__all__ = ["VALIDATION_POLICY", "build_validation_policy"]
