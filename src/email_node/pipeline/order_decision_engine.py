from __future__ import annotations

from email_node.shared_pipeline_core.decision import (
    SharedDecisionEngine,
    SharedDecisionPolicy,
    SharedDecisionResult,
)


class OrderDecisionResult(SharedDecisionResult):
    pass


class OrderDecisionEngine(SharedDecisionEngine):
    def __init__(self, policy: SharedDecisionPolicy | None = None) -> None:
        super().__init__(policy=policy or SharedDecisionPolicy())
