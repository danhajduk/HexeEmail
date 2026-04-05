from __future__ import annotations

from email_node.patterns.probation_policy import ProbationPromotionPolicy
from email_node.patterns.probation_state import ProbationTemplateState
from email_node.patterns.template_promotion_service import TemplatePromotionService, TemplatePromotionServiceError


class ProbationPromotionManager:
    def __init__(
        self,
        *,
        promotion_service: TemplatePromotionService,
        policy: ProbationPromotionPolicy | None = None,
    ) -> None:
        self.promotion_service = promotion_service
        self.policy = policy or ProbationPromotionPolicy()

    def evaluate_and_apply(self, state: ProbationTemplateState) -> ProbationTemplateState:
        if self.policy.is_promotion_eligible(state):
            try:
                self.promotion_service.promote(state.template_id)
            except TemplatePromotionServiceError as exc:
                return state.model_copy(
                    update={
                        "promotion_eligible": True,
                        "promotion_reason": f"Promotion blocked: {exc}",
                    }
                )
            return state.model_copy(
                update={
                    "status": "active",
                    "promotion_eligible": True,
                    "promotion_reason": "Template promoted after meeting probation thresholds.",
                }
            )
        if self.policy.should_reject_template(state):
            return state.model_copy(
                update={
                    "status": "rejected",
                    "promotion_eligible": False,
                    "promotion_reason": "Rejected due to repeated hard failures.",
                }
            )
        if self.policy.should_mark_for_refinement(state):
            return state.model_copy(
                update={
                    "promotion_eligible": False,
                    "promotion_reason": "Needs refinement before promotion.",
                }
            )
        return state.model_copy(
            update={
                "promotion_eligible": False,
                "promotion_reason": "Awaiting more probation samples.",
            }
        )
