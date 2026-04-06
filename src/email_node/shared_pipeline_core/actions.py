from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from email_node.shared_pipeline_core.decision import SharedDecisionResult


class SharedActionAuthorizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions_allowed: bool
    blocked_reason: str | None = None
    decision: str
    extraction_source: str
    diagnostics: list[str] = Field(default_factory=list)


class SharedActionGate:
    def authorize(self, *, decision: SharedDecisionResult, phase4) -> SharedActionAuthorizationResult:
        diagnostics = list(decision.diagnostics)
        extraction_source = decision.extraction_source
        if self.is_allowed(decision=decision, phase4=phase4):
            return SharedActionAuthorizationResult(
                actions_allowed=True,
                decision=decision.decision,
                extraction_source=extraction_source,
                diagnostics=diagnostics + ["action_gate:allowed"],
            )
        blocked_reason = self.blocked_reason(decision=decision, phase4=phase4)
        return SharedActionAuthorizationResult(
            actions_allowed=False,
            blocked_reason=blocked_reason,
            decision=decision.decision,
            extraction_source=extraction_source,
            diagnostics=diagnostics + [f"action_gate:blocked:{blocked_reason}"],
        )

    @staticmethod
    def is_allowed(*, decision: SharedDecisionResult, phase4) -> bool:
        return bool(
            decision.decision == "accept"
            and decision.allow_downstream_actions
            and decision.extraction_source == "active"
        )

    @staticmethod
    def blocked_reason(*, decision: SharedDecisionResult, phase4) -> str:
        if decision.decision == "probation":
            return "decision_probation"
        if decision.decision == "reject":
            return f"decision_reject:{decision.decision_reason}"
        if decision.extraction_source != "active":
            return f"blocked_extraction_source:{decision.extraction_source}"
        if not getattr(phase4, "extracted_fields", {}):
            return "missing_structured_extraction"
        return "policy_blocked"


SharedActionIntent = str


class SharedActionRoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_intents: list[SharedActionIntent] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class SharedActionRouter:
    def route(
        self,
        *,
        decision: SharedDecisionResult,
        authorization: SharedActionAuthorizationResult,
        phase4,
    ) -> SharedActionRoutingResult:
        diagnostics = list(decision.diagnostics) + list(authorization.diagnostics)
        if not authorization.actions_allowed:
            return SharedActionRoutingResult(action_intents=[], diagnostics=diagnostics + ["action_router:blocked"])
        intents = list(self.resolve_action_intents(decision=decision, authorization=authorization, phase4=phase4))
        deduped = list(dict.fromkeys(str(intent) for intent in intents if str(intent).strip()))
        return SharedActionRoutingResult(
            action_intents=deduped,
            diagnostics=diagnostics + [f"action_router:intents:{','.join(deduped) or 'none'}"],
        )

    def resolve_action_intents(
        self,
        *,
        decision: SharedDecisionResult,
        authorization: SharedActionAuthorizationResult,
        phase4,
    ) -> list[SharedActionIntent]:
        raise NotImplementedError
