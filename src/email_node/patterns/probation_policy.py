from __future__ import annotations

from dataclasses import dataclass

from email_node.patterns.probation_state import ProbationTemplateState


@dataclass(frozen=True)
class ProbationPromotionPolicy:
    minimum_sample_count: int = 5
    required_field_success_rate: float = 0.90
    high_requires_success_rate: float = 0.80
    hard_failure_count_max: int = 1

    def is_promotion_eligible(self, state: ProbationTemplateState) -> bool:
        return (
            state.sample_count >= self.minimum_sample_count
            and state.required_field_success_rate >= self.required_field_success_rate
            and state.high_requires_success_rate >= self.high_requires_success_rate
            and state.hard_failure_count <= self.hard_failure_count_max
        )

    def should_reject_template(self, state: ProbationTemplateState) -> bool:
        if state.sample_count < self.minimum_sample_count:
            return False
        return state.hard_failure_count > self.hard_failure_count_max + 1

    def should_mark_for_refinement(self, state: ProbationTemplateState) -> bool:
        if state.sample_count < self.minimum_sample_count:
            return False
        if self.is_promotion_eligible(state) or self.should_reject_template(state):
            return False
        return (
            state.required_field_success_rate < self.required_field_success_rate
            or state.high_requires_success_rate < self.high_requires_success_rate
        )

    def should_remain_on_probation(self, state: ProbationTemplateState) -> bool:
        return not self.is_promotion_eligible(state) and not self.should_mark_for_refinement(state) and not self.should_reject_template(state)
