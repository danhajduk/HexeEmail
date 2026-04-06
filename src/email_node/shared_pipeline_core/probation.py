from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from email_node.patterns.probation_evaluation_result import ProbationEvaluationResult
from email_node.patterns.probation_state import ProbationTemplateState
from email_node.patterns.probation_store import ProbationStore
from email_node.patterns.template_promotion_service import TemplatePromotionService, TemplatePromotionServiceError
from logging_utils import get_logger


LOGGER = get_logger(__name__)


class SharedProbationExtractor(Protocol):
    def build_working_object(self, phase3) -> tuple[object | None, str | None]: ...

    def run_template(self, working: object, template: dict[str, object]) -> tuple[dict[str, object], list[str], list[str]]: ...

    def validate_fields(self, extracted_fields: dict[str, object], *, required_fields: object) -> tuple[dict[str, object], list[str]]: ...

    def score_extraction_confidence(
        self,
        extracted_fields: dict[str, object],
        *,
        required_fields: object,
    ) -> tuple[float, str, list[str], str]: ...

    def _is_missing_value(self, value: object | None) -> bool: ...


class SharedProbationEvaluator:
    def __init__(
        self,
        *,
        probation_store: ProbationStore,
        extractor: SharedProbationExtractor,
    ) -> None:
        self.probation_store = probation_store
        self.extractor = extractor

    def evaluate(self, phase3, *, template_id: str) -> ProbationEvaluationResult:
        template = self.probation_store.load_template_payload(template_id)
        evaluated_at = getattr(phase3, "message_id", None)
        from datetime import UTC, datetime

        evaluated_ts = datetime.now(UTC)
        if not isinstance(template, dict):
            result = ProbationEvaluationResult(
                template_id=template_id,
                message_id=phase3.message_id,
                profile_id=str(getattr(phase3, "profile_id", "") or "unknown"),
                matched=False,
                extraction_succeeded=False,
                required_fields_present=False,
                high_requires_present=False,
                confidence_score=0.0,
                hard_failure=True,
                failure_reason="template_missing",
                evaluated_at=evaluated_ts,
            )
            self.probation_store.save_evaluation(result)
            return result

        working, intake_error = self.extractor.build_working_object(phase3)
        if working is None:
            result = ProbationEvaluationResult(
                template_id=template_id,
                message_id=phase3.message_id,
                profile_id=str(getattr(phase3, "profile_id", "") or "unknown"),
                matched=False,
                extraction_succeeded=False,
                required_fields_present=False,
                high_requires_present=False,
                confidence_score=0.0,
                hard_failure=True,
                failure_reason=intake_error or "phase3_not_ready",
                evaluated_at=evaluated_ts,
            )
            self.probation_store.save_evaluation(result)
            return result

        profile_id = str(template.get("profile_id") or "")
        vendor_identity = ""
        match = template.get("match")
        if isinstance(match, dict):
            vendor_identity = str(match.get("vendor_identity") or "").strip()
        working_profile_id = str(getattr(working, "profile_id", "") or "")
        working_vendor_identity = str(getattr(working, "vendor_identity", "") or "")
        matched = (not profile_id or profile_id == working_profile_id) and (
            not vendor_identity or vendor_identity == working_vendor_identity
        )
        if not matched:
            result = ProbationEvaluationResult(
                template_id=template_id,
                message_id=phase3.message_id,
                profile_id=working_profile_id or str(getattr(phase3, "profile_id", "") or "unknown"),
                matched=False,
                extraction_succeeded=False,
                required_fields_present=False,
                high_requires_present=False,
                confidence_score=0.0,
                hard_failure=True,
                failure_reason="template_profile_or_vendor_mismatch",
                evaluated_at=evaluated_ts,
            )
            self.probation_store.save_evaluation(result)
            return result

        extracted_fields, _, _ = self.extractor.run_template(working, template)
        required_fields = [str(item) for item in template.get("required_fields", []) or []]
        confidence_rules = template.get("confidence_rules")
        high_requires = []
        if isinstance(confidence_rules, dict):
            high_requires = [str(item) for item in confidence_rules.get("high_requires", []) or []]
        extracted_fields, validation_diagnostics = self.extractor.validate_fields(
            extracted_fields,
            required_fields=required_fields,
        )
        confidence_score, _, _, extraction_status = self.extractor.score_extraction_confidence(
            extracted_fields,
            required_fields=required_fields,
        )
        missing_required_fields = [
            field_name
            for field_name in required_fields
            if field_name not in extracted_fields or self.extractor._is_missing_value(getattr(extracted_fields[field_name], "value", None))
        ]
        missing_high_requires = [
            field_name
            for field_name in high_requires
            if field_name not in extracted_fields or self.extractor._is_missing_value(getattr(extracted_fields[field_name], "value", None))
        ]
        result = ProbationEvaluationResult(
            template_id=template_id,
            message_id=phase3.message_id,
            profile_id=working_profile_id or str(getattr(phase3, "profile_id", "") or "unknown"),
            matched=True,
            extraction_succeeded=extraction_status in {"success", "partial"},
            required_fields_present=not missing_required_fields,
            missing_required_fields=missing_required_fields,
            high_requires_present=not missing_high_requires,
            missing_high_requires=missing_high_requires,
            extracted_fields={
                name: (field.value if hasattr(field, "value") else field)
                for name, field in extracted_fields.items()
            },
            confidence_score=confidence_score,
            hard_failure=any(item.startswith("invalid_field:") for item in validation_diagnostics),
            failure_reason=None if not validation_diagnostics else ",".join(validation_diagnostics),
            evaluated_at=evaluated_ts,
        )
        self.probation_store.save_evaluation(result)
        return result


class SharedProbationMetrics:
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


@dataclass(frozen=True)
class SharedProbationPromotionPolicy:
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


class SharedProbationPromotionManager:
    def __init__(
        self,
        *,
        promotion_service: TemplatePromotionService,
        policy: SharedProbationPromotionPolicy | None = None,
    ) -> None:
        self.promotion_service = promotion_service
        self.policy = policy or SharedProbationPromotionPolicy()

    def evaluate_and_apply(self, state: ProbationTemplateState) -> ProbationTemplateState:
        if self.policy.is_promotion_eligible(state):
            try:
                self.promotion_service.promote(state.template_id)
            except TemplatePromotionServiceError as exc:
                updated_state = state.model_copy(
                    update={
                        "promotion_eligible": True,
                        "promotion_reason": f"Promotion blocked: {exc}",
                    }
                )
                LOGGER.info(
                    "Probation promotion blocked",
                    extra={"event_data": {"template_id": state.template_id, "status": updated_state.status, "promotion_reason": updated_state.promotion_reason}},
                )
                return updated_state
            updated_state = state.model_copy(
                update={
                    "status": "active",
                    "promotion_eligible": True,
                    "promotion_reason": "Template promoted after meeting probation thresholds.",
                }
            )
            LOGGER.info(
                "Probation promotion decision",
                extra={"event_data": {"template_id": state.template_id, "status": updated_state.status, "promotion_eligible": updated_state.promotion_eligible, "promotion_reason": updated_state.promotion_reason}},
            )
            return updated_state
        if self.policy.should_reject_template(state):
            updated_state = state.model_copy(
                update={"status": "rejected", "promotion_eligible": False, "promotion_reason": "Rejected due to repeated hard failures."}
            )
            LOGGER.info(
                "Probation promotion decision",
                extra={"event_data": {"template_id": state.template_id, "status": updated_state.status, "promotion_eligible": updated_state.promotion_eligible, "promotion_reason": updated_state.promotion_reason}},
            )
            return updated_state
        if self.policy.should_mark_for_refinement(state):
            updated_state = state.model_copy(
                update={"promotion_eligible": False, "promotion_reason": "Needs refinement before promotion."}
            )
            LOGGER.info(
                "Probation promotion decision",
                extra={"event_data": {"template_id": state.template_id, "status": updated_state.status, "promotion_eligible": updated_state.promotion_eligible, "promotion_reason": updated_state.promotion_reason}},
            )
            return updated_state
        updated_state = state.model_copy(
            update={"promotion_eligible": False, "promotion_reason": "Awaiting more probation samples."}
        )
        LOGGER.info(
            "Probation promotion decision",
            extra={"event_data": {"template_id": state.template_id, "status": updated_state.status, "promotion_eligible": updated_state.promotion_eligible, "promotion_reason": updated_state.promotion_reason}},
        )
        return updated_state


def build_probation_shadow_comparison(phase4, evaluation: ProbationEvaluationResult) -> dict[str, object]:
    active_fields = {
        field_name: (field.value if hasattr(field, "value") else field.get("value") if isinstance(field, dict) else field)
        for field_name, field in getattr(phase4, "extracted_fields", {}).items()
    }
    probation_fields = dict(evaluation.extracted_fields)
    all_field_names = sorted(set(active_fields) | set(probation_fields))
    extraction_variance = {
        field_name: {
            "active": active_fields.get(field_name),
            "probation": probation_fields.get(field_name),
        }
        for field_name in all_field_names
        if active_fields.get(field_name) != probation_fields.get(field_name)
    }
    differing_required_fields = sorted(set(evaluation.missing_required_fields))
    differing_high_requires = sorted(set(evaluation.missing_high_requires))
    return {
        "message_id": phase4.message_id,
        "active_template_id": phase4.template_id,
        "probation_template_id": evaluation.template_id,
        "profile_id": phase4.profile_id,
        "required_field_differences": differing_required_fields,
        "high_requires_differences": differing_high_requires,
        "extraction_variance": extraction_variance,
    }
