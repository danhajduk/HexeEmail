from __future__ import annotations

from email_node.shared_pipeline_core.decision import SharedDecisionPolicy


DECISION_POLICY = SharedDecisionPolicy(
    high_confidence_threshold=0.85,
    medium_confidence_threshold=0.60,
)


def build_decision_policy() -> SharedDecisionPolicy:
    return DECISION_POLICY
