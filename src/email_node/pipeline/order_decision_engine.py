from __future__ import annotations

from email_node.shared_pipeline_core import get_flow_family_config, load_decision_policy
from email_node.shared_pipeline_core.decision import (
    SharedDecisionEngine,
    SharedDecisionPolicy,
    SharedDecisionResult,
)


class OrderDecisionResult(SharedDecisionResult):
    pass


class OrderDecisionEngine(SharedDecisionEngine):
    def __init__(self, policy: SharedDecisionPolicy | None = None) -> None:
        flow_config = get_flow_family_config("order")
        super().__init__(policy=policy or load_decision_policy(flow_config.decision_policy))
