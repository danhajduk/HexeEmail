from __future__ import annotations

from datetime import UTC, datetime

from email_node.patterns.probation_evaluation_result import ProbationEvaluationResult
from email_node.patterns.probation_store import ProbationStore
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


class ProbationEvaluator:
    def __init__(
        self,
        *,
        probation_store: ProbationStore,
        extractor: GmailOrderPhase4Extractor | None = None,
    ) -> None:
        self.probation_store = probation_store
        self.extractor = extractor or GmailOrderPhase4Extractor()

    def evaluate(self, phase3, *, template_id: str) -> ProbationEvaluationResult:
        template = self.probation_store.load_template_payload(template_id)
        evaluated_at = datetime.now(UTC)
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
                evaluated_at=evaluated_at,
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
                evaluated_at=evaluated_at,
            )
            self.probation_store.save_evaluation(result)
            return result

        profile_id = str(template.get("profile_id") or "")
        vendor_identity = ""
        match = template.get("match")
        if isinstance(match, dict):
            vendor_identity = str(match.get("vendor_identity") or "").strip()
        matched = (not profile_id or profile_id == working.profile_id) and (
            not vendor_identity or vendor_identity == (working.vendor_identity or "")
        )
        if not matched:
            result = ProbationEvaluationResult(
                template_id=template_id,
                message_id=phase3.message_id,
                profile_id=working.profile_id,
                matched=False,
                extraction_succeeded=False,
                required_fields_present=False,
                high_requires_present=False,
                confidence_score=0.0,
                hard_failure=True,
                failure_reason="template_profile_or_vendor_mismatch",
                evaluated_at=evaluated_at,
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
            if field_name not in extracted_fields or self.extractor._is_missing_value(extracted_fields[field_name].value)
        ]
        missing_high_requires = [
            field_name
            for field_name in high_requires
            if field_name not in extracted_fields or self.extractor._is_missing_value(extracted_fields[field_name].value)
        ]
        result = ProbationEvaluationResult(
            template_id=template_id,
            message_id=phase3.message_id,
            profile_id=working.profile_id,
            matched=True,
            extraction_succeeded=extraction_status in {"success", "partial"},
            required_fields_present=not missing_required_fields,
            missing_required_fields=missing_required_fields,
            high_requires_present=not missing_high_requires,
            missing_high_requires=missing_high_requires,
            extracted_fields={name: field.value for name, field in extracted_fields.items()},
            confidence_score=confidence_score,
            hard_failure=any(item.startswith("invalid_field:") for item in validation_diagnostics),
            failure_reason=None if not validation_diagnostics else ",".join(validation_diagnostics),
            evaluated_at=evaluated_at,
        )
        self.probation_store.save_evaluation(result)
        return result
