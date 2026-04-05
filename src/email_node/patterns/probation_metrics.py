from __future__ import annotations

from email_node.patterns.probation_evaluation_result import ProbationEvaluationResult
from email_node.patterns.probation_state import ProbationTemplateState


class ProbationMetrics:
    @staticmethod
    def update_state(
        state: ProbationTemplateState,
        result: ProbationEvaluationResult,
    ) -> ProbationTemplateState:
        next_sample_count = state.sample_count + 1
        required_successes = (state.required_field_success_rate * state.sample_count) + (
            1 if result.required_fields_present and not result.hard_failure else 0
        )
        high_requires_successes = (state.high_requires_success_rate * state.sample_count) + (
            1 if result.high_requires_present and not result.hard_failure else 0
        )
        success = result.required_fields_present and result.extraction_succeeded and not result.hard_failure
        failure = result.hard_failure or (not result.required_fields_present) or (not result.extraction_succeeded)
        return state.model_copy(
            update={
                "sample_count": next_sample_count,
                "success_count": state.success_count + (1 if success else 0),
                "failure_count": state.failure_count + (1 if failure else 0),
                "hard_failure_count": state.hard_failure_count + (1 if result.hard_failure else 0),
                "required_field_success_rate": round(required_successes / next_sample_count, 4),
                "high_requires_success_rate": round(high_requires_successes / next_sample_count, 4),
                "last_evaluated_at": result.evaluated_at,
                "updated_at": result.evaluated_at,
            }
        )
