from __future__ import annotations

from datetime import UTC, datetime

from email_node.patterns import PatternGenerationRequest, ProbationStore, ProbationTemplateState
from email_node.shared_pipeline_core import build_probation_shadow_comparison
from email_node.shared_pipeline_core.probation import (
    SharedProbationEvaluator,
    SharedProbationMetrics,
    SharedProbationPromotionManager,
)


class SharedFamilyProbationRuntimeMixin:
    probation_store: ProbationStore
    probation_evaluator: SharedProbationEvaluator
    probation_promotion: SharedProbationPromotionManager
    generate_probation_template: object
    ai_calls_enabled: object
    phase4_extractor: object

    async def attach_probation_template(self, phase4):
        if not self._should_attempt_probation(phase4):
            return phase4
        profile_id = self._probation_profile_id(phase4)
        vendor_identity = self._probation_vendor_identity(phase4)
        existing_state = self.probation_store.find_state(
            profile_id=profile_id or None,
            vendor_identity=vendor_identity or None,
            status="probation",
        )
        if existing_state is not None:
            evaluation = self.probation_evaluator.evaluate(
                self._phase3_with_probation_profile(phase4, template_id=existing_state.template_id),
                template_id=existing_state.template_id,
            )
            updated_state = SharedProbationMetrics.update_state(existing_state, evaluation)
            updated_state = updated_state.model_copy(
                update={
                    "last_generation_attempt_at": datetime.now(UTC),
                    "last_generation_result": "skipped_existing_probation",
                }
            )
            updated_state = self.probation_promotion.evaluate_and_apply(updated_state)
            self.probation_store.save_state(updated_state)
            updated_phase4 = phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [
                        f"probation_template:existing:{existing_state.template_id}",
                        f"probation_template:evaluated:{existing_state.template_id}:{'hard_failure' if evaluation.hard_failure else 'ok'}",
                        f"probation_template:state:{existing_state.template_id}:{updated_state.status}",
                    ]
                }
            )
            if evaluation.extraction_succeeded and evaluation.extracted_fields:
                updated_phase4 = self._apply_probation_template(updated_phase4, template_id=existing_state.template_id)
            return updated_phase4
        if not self.ai_calls_enabled():
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + ["probation_template:skipped_ai_disabled"]
                }
            )
        generate_probation_template = getattr(self, "generate_probation_template", None)
        if generate_probation_template is None:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + ["probation_template:skipped_no_generator"]
                }
            )
        try:
            request = self._build_probation_request(phase4)
        except ValueError as exc:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:request_build_failed:{exc}"]
                }
            )
        try:
            result = await generate_probation_template(request)
        except Exception as exc:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:generation_failed:{exc}"]
                }
            )
        template_id = str(result.get("template_id") or request.template_id).strip() or request.template_id
        now = datetime.now(UTC)
        self.probation_store.save_state(
            self.probation_store.load_state(template_id)
            or ProbationTemplateState(
                template_id=template_id,
                profile_id=request.profile_id,
                template_version=request.template_version,
                created_at=now,
                updated_at=now,
                sample_count=1,
                success_count=0,
                failure_count=0,
                hard_failure_count=0,
                required_field_success_rate=0.0,
                high_requires_success_rate=0.0,
                last_generation_attempt_at=now,
                last_generation_result="created",
                promotion_eligible=False,
                promotion_reason="Awaiting probation evaluation.",
            )
        )
        return phase4.model_copy(
            update={
                "template_diagnostics": list(phase4.template_diagnostics)
                + [f"probation_template:created:{template_id}"]
            }
        )

    def run_probation_shadow_mode(self, phase4):
        if not getattr(phase4, "template_id", None):
            return phase4
        probation_state = self.probation_store.find_state(
            profile_id=self._probation_profile_id(phase4) or None,
            vendor_identity=self._probation_vendor_identity(phase4) or None,
            status="probation",
        )
        if probation_state is None:
            return phase4
        evaluation = self.probation_evaluator.evaluate(
            self._phase3_with_probation_profile(phase4, template_id=probation_state.template_id),
            template_id=probation_state.template_id,
        )
        updated_state = SharedProbationMetrics.update_state(probation_state, evaluation)
        updated_state = self.probation_promotion.evaluate_and_apply(updated_state)
        self.probation_store.save_state(updated_state)
        comparison = build_probation_shadow_comparison(phase4, evaluation)
        self.probation_store.save_shadow_comparison(probation_state.template_id, phase4.message_id, comparison)
        return phase4.model_copy(
            update={
                "template_diagnostics": list(phase4.template_diagnostics)
                + [
                    f"probation_template:shadow:{probation_state.template_id}",
                    f"probation_template:state:{probation_state.template_id}:{updated_state.status}",
                ]
            }
        )

    @staticmethod
    def _should_attempt_probation(phase4) -> bool:
        extraction_status = str(getattr(phase4, "extraction_status", "") or "")
        return extraction_status in {"failed", "unresolved"}

    @staticmethod
    def _probation_profile_id(phase4) -> str:
        return str(getattr(phase4, "profile_id", "") or "").strip()

    @staticmethod
    def _probation_vendor_identity(phase4) -> str:
        return str(
            getattr(phase4, "vendor_identity", None)
            or getattr(phase4, "sender_domain", None)
            or ""
        ).strip().lower()

    @staticmethod
    def _phase3_with_probation_profile(phase4, *, template_id: str):
        phase3 = getattr(phase4, "phase3_reference", None)
        if phase3 is None:
            return phase4
        return phase3.model_copy(
            update={
                "profile_id": getattr(phase4, "profile_id", None) or getattr(phase3, "profile_id", None),
                "profile_family": getattr(phase4, "profile_family", None) or getattr(phase3, "profile_family", None),
                "profile_subtype": getattr(phase4, "profile_subtype", None) or getattr(phase3, "profile_subtype", None),
                "vendor_identity": getattr(phase4, "vendor_identity", None) or getattr(phase3, "vendor_identity", None),
                "template_candidate_id": template_id,
            }
        )

    def _apply_probation_template(self, phase4, *, template_id: str):
        template = self.probation_store.load_template_payload(template_id)
        if not isinstance(template, dict):
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:apply_skipped_missing_template:{template_id}"]
                }
            )
        working, intake_error = self.phase4_extractor.build_working_object(
            self._phase3_with_probation_profile(phase4, template_id=template_id)
        )
        if working is None:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:apply_failed:{template_id}:{intake_error or 'phase3_not_ready'}"]
                }
            )

        extracted_fields, field_diagnostics, template_execution_diagnostics = self.phase4_extractor.run_template(working, template)
        required_fields = template.get("required_fields", [])
        extracted_fields, validation_diagnostics = self.phase4_extractor.validate_fields(
            extracted_fields,
            required_fields=required_fields,
        )
        confidence, _, confidence_diagnostics, extraction_status = self.phase4_extractor.score_extraction_confidence(
            extracted_fields,
            required_fields=required_fields,
        )
        if extraction_status not in {"success", "partial"} or not extracted_fields:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:apply_skipped_unusable:{template_id}"]
                }
            )

        probation_confidence = round(min(max(confidence, 0.0), 0.49), 2)
        template_diagnostics = [
            item
            for item in list(phase4.template_diagnostics)
            if item != "template_execution:skipped_no_template" and item != "confidence:unresolved_no_template"
        ]
        template_diagnostics.extend(
            template_execution_diagnostics
            + validation_diagnostics
            + confidence_diagnostics
            + [f"probation_template:applied:{template_id}"]
        )
        stage_statuses = {
            **dict(phase4.stage_statuses),
            "template_execution": "partial",
            "field_validation": "partial",
            "confidence_scoring": "partial",
        }
        stage_diagnostics = {
            **dict(phase4.stage_diagnostics),
            "template_execution": self.phase4_extractor._diagnostics(template_execution_diagnostics),
            "field_validation": self.phase4_extractor._diagnostics(validation_diagnostics),
            "confidence_scoring": self.phase4_extractor._diagnostics(
                confidence_diagnostics + [f"confidence_downgrade:probation_template:{template_id}"]
            ),
        }
        return phase4.model_copy(
            update={
                "template_id": template_id,
                "template_version": str(template.get("template_version") or phase4.template_version or "v1"),
                "extraction_status": "partial",
                "extraction_confidence": probation_confidence,
                "extraction_confidence_level": "low",
                "extracted_fields": extracted_fields,
                "field_diagnostics": field_diagnostics + validation_diagnostics,
                "template_diagnostics": template_diagnostics,
                "stage_statuses": stage_statuses,
                "stage_diagnostics": stage_diagnostics,
            }
        )

    def _build_probation_request(self, phase4) -> PatternGenerationRequest:
        raise NotImplementedError
