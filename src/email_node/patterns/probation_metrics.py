from __future__ import annotations

from email_node.patterns.probation_evaluation_result import ProbationEvaluationResult
from email_node.patterns.probation_state import ProbationTemplateState
from logging_utils import get_logger


LOGGER = get_logger(__name__)


class ProbationMetrics:
    @staticmethod
    def update_state(
        state: ProbationTemplateState,
        result: ProbationEvaluationResult,
    ) -> ProbationTemplateState:
        next_sample_count = state.sample_count + 1
        evaluated_sample_count = max(0, state.sample_count - 1)
        next_evaluated_sample_count = evaluated_sample_count + 1
        required_successes = (state.required_field_success_rate * evaluated_sample_count) + (
            1 if result.required_fields_present and not result.hard_failure else 0
        )
        high_requires_successes = (state.high_requires_success_rate * evaluated_sample_count) + (
            1 if result.high_requires_present and not result.hard_failure else 0
        )
        success = result.required_fields_present and result.extraction_succeeded and not result.hard_failure
        failure = result.hard_failure or (not result.required_fields_present) or (not result.extraction_succeeded)
        updated_state = state.model_copy(
            update={
                "sample_count": next_sample_count,
                "success_count": state.success_count + (1 if success else 0),
                "failure_count": state.failure_count + (1 if failure else 0),
                "hard_failure_count": state.hard_failure_count + (1 if result.hard_failure else 0),
                "required_field_success_rate": round(required_successes / next_evaluated_sample_count, 4),
                "high_requires_success_rate": round(high_requires_successes / next_evaluated_sample_count, 4),
                "last_evaluated_at": result.evaluated_at,
                "updated_at": result.evaluated_at,
            }
        )
        LOGGER.info(
            "Probation metrics updated",
            extra={
                "event_data": {
                    "template_id": state.template_id,
                    "message_id": result.message_id,
                    "sample_count": updated_state.sample_count,
                    "success_count": updated_state.success_count,
                    "failure_count": updated_state.failure_count,
                    "hard_failure_count": updated_state.hard_failure_count,
                    "required_field_success_rate": updated_state.required_field_success_rate,
                    "high_requires_success_rate": updated_state.high_requires_success_rate,
                }
            },
        )
        return updated_state
