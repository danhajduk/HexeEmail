from __future__ import annotations

from email_node.pipeline.order_action_gate import OrderActionAuthorizationResult
from email_node.pipeline.order_decision_engine import OrderDecisionResult
from email_node.shared_pipeline_core import get_flow_family_config, load_action_routing_policy
from email_node.shared_pipeline_core.actions import SharedActionIntent, SharedActionRoutingResult, SharedPolicyActionRouter


OrderActionIntent = SharedActionIntent


class OrderActionRoutingResult(SharedActionRoutingResult):
    pass


class OrderActionRouter(SharedPolicyActionRouter):
    def __init__(self) -> None:
        flow_config = get_flow_family_config("order")
        super().__init__(policy=load_action_routing_policy(flow_config.action_router_policy))

    def route(
        self,
        *,
        decision: OrderDecisionResult,
        authorization: OrderActionAuthorizationResult,
        phase4,
    ) -> OrderActionRoutingResult:
        result = super().route(decision=decision, authorization=authorization, phase4=phase4)
        return OrderActionRoutingResult.model_validate(result.model_dump(mode="json"))
