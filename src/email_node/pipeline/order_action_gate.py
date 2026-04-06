from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from email_node.pipeline.order_decision_engine import OrderDecisionResult


class OrderActionAuthorizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions_allowed: bool
    blocked_reason: str | None = None
    decision: str
    extraction_source: str
    diagnostics: list[str] = Field(default_factory=list)


class OrderActionGate:
    def authorize(self, *, decision: OrderDecisionResult, phase4) -> OrderActionAuthorizationResult:
        diagnostics = list(decision.diagnostics)
        extraction_source = decision.extraction_source
        if decision.decision == "accept" and decision.allow_downstream_actions and extraction_source == "active":
            return OrderActionAuthorizationResult(
                actions_allowed=True,
                decision=decision.decision,
                extraction_source=extraction_source,
                diagnostics=diagnostics + ["action_gate:allowed"],
            )
        blocked_reason = self._blocked_reason(decision=decision, phase4=phase4)
        return OrderActionAuthorizationResult(
            actions_allowed=False,
            blocked_reason=blocked_reason,
            decision=decision.decision,
            extraction_source=extraction_source,
            diagnostics=diagnostics + [f"action_gate:blocked:{blocked_reason}"],
        )

    @staticmethod
    def _blocked_reason(*, decision: OrderDecisionResult, phase4) -> str:
        if decision.decision == "probation":
            return "decision_probation"
        if decision.decision == "reject":
            return f"decision_reject:{decision.decision_reason}"
        if decision.extraction_source != "active":
            return f"blocked_extraction_source:{decision.extraction_source}"
        if not getattr(phase4, "extracted_fields", {}):
            return "missing_structured_extraction"
        return "policy_blocked"
