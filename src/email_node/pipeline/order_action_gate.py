from __future__ import annotations

from email_node.pipeline.order_decision_engine import OrderDecisionResult
from email_node.shared_pipeline_core.actions import SharedActionAuthorizationResult, SharedActionGate


class OrderActionAuthorizationResult(SharedActionAuthorizationResult):
    pass


class OrderActionGate(SharedActionGate):
    def authorize(self, *, decision: OrderDecisionResult, phase4) -> OrderActionAuthorizationResult:
        result = super().authorize(decision=decision, phase4=phase4)
        return OrderActionAuthorizationResult.model_validate(result.model_dump(mode="json"))
