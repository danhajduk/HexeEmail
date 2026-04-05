from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Awaitable, Callable

from email_node.patterns import PatternGenerationRequest
from email_node.patterns.probation_evaluator import ProbationEvaluator
from email_node.patterns.probation_metrics import ProbationMetrics
from email_node.patterns.probation_policy import ProbationPromotionPolicy
from email_node.patterns.probation_promotion import ProbationPromotionManager
from email_node.patterns.probation_state import ProbationTemplateState
from email_node.patterns.probation_store import ProbationStore
from email_node.patterns.template_promotion_service import TemplatePromotionService
from providers.gmail.order_phase2 import GmailOrderPhase2Scrubber
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


class OrderFlowPipeline:
    def __init__(
        self,
        *,
        phase2_scrubber: GmailOrderPhase2Scrubber | None = None,
        phase3_detector: GmailOrderPhase3ProfileDetector | None = None,
        phase4_extractor: GmailOrderPhase4Extractor | None = None,
        probation_store: ProbationStore | None = None,
        probation_evaluator: ProbationEvaluator | None = None,
        probation_promotion: ProbationPromotionManager | None = None,
        generate_probation_template: Callable[[PatternGenerationRequest], Awaitable[dict[str, object]]] | None = None,
        ai_calls_enabled: Callable[[], bool] | None = None,
    ) -> None:
        self.phase2_scrubber = phase2_scrubber or GmailOrderPhase2Scrubber()
        self.phase3_detector = phase3_detector or GmailOrderPhase3ProfileDetector()
        self.phase4_extractor = phase4_extractor or GmailOrderPhase4Extractor()
        self.probation_store = probation_store or ProbationStore()
        self.probation_evaluator = probation_evaluator or ProbationEvaluator(probation_store=self.probation_store)
        self.probation_promotion = probation_promotion or ProbationPromotionManager(
            promotion_service=TemplatePromotionService(probation_store=self.probation_store),
            policy=ProbationPromotionPolicy(),
        )
        self.generate_probation_template = generate_probation_template
        self.ai_calls_enabled = ai_calls_enabled or (lambda: True)

    async def process_normalized_email(self, normalized) -> dict[str, object]:
        phase2 = self.phase2_scrubber.scrub(normalized)
        phase3 = self.phase3_detector.detect(phase2)
        phase4 = self.phase4_extractor.extract(phase3)
        phase4 = await self.attach_probation_template(phase4)
        phase4 = self._run_probation_shadow_mode(phase4)
        return {
            "phase2": phase2,
            "phase3": phase3,
            "phase4": phase4,
        }

    async def attach_probation_template(self, phase4):
        if not self._should_attempt_probation(phase4):
            return phase4
        if not self.ai_calls_enabled():
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics) + ["probation_template:skipped_ai_disabled"]
                }
            )
        if self.generate_probation_template is None:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics) + ["probation_template:skipped_no_generator"]
                }
            )
        try:
            request = self._build_pattern_generation_request(phase4)
        except ValueError as exc:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:request_build_failed:{exc}"]
                }
            )

        existing_state = self.probation_store.find_state(
            profile_id=request.profile_id,
            vendor_identity=request.vendor_identity,
            status="probation",
        )
        if existing_state is not None:
            evaluation = self.probation_evaluator.evaluate(phase4.phase3_reference, template_id=existing_state.template_id)
            updated_state = ProbationMetrics.update_state(existing_state, evaluation)
            updated_state = self.probation_promotion.evaluate_and_apply(updated_state)
            self.probation_store.save_state(updated_state)
            promotion_suffix = updated_state.status
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [
                        f"probation_template:existing:{existing_state.template_id}",
                        f"probation_template:evaluated:{existing_state.template_id}:{'hard_failure' if evaluation.hard_failure else 'ok'}",
                        f"probation_template:state:{existing_state.template_id}:{promotion_suffix}",
                    ]
                }
            )

        try:
            result = await self.generate_probation_template(request)
        except Exception as exc:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:generation_failed:{exc}"]
                }
            )

        template_id = str(result.get("template_id") or request.template_id).strip() or request.template_id
        now = datetime.now(UTC)
        state = ProbationTemplateState(
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
            promotion_eligible=False,
            promotion_reason="Awaiting probation evaluation.",
        )
        self.probation_store.save_state(state)
        return phase4.model_copy(
            update={
                "template_diagnostics": list(phase4.template_diagnostics) + [f"probation_template:created:{template_id}"]
            }
        )

    def _run_probation_shadow_mode(self, phase4):
        if not getattr(phase4, "template_id", None):
            return phase4
        probation_state = self.probation_store.find_state(
            profile_id=getattr(phase4, "profile_id", None),
            vendor_identity=getattr(phase4, "vendor_identity", None),
            status="probation",
        )
        if probation_state is None:
            return phase4
        evaluation = self.probation_evaluator.evaluate(phase4.phase3_reference, template_id=probation_state.template_id)
        updated_state = ProbationMetrics.update_state(probation_state, evaluation)
        updated_state = self.probation_promotion.evaluate_and_apply(updated_state)
        self.probation_store.save_state(updated_state)
        comparison = self._build_shadow_comparison(phase4, evaluation)
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
        if getattr(phase4, "extraction_status", None) != "unresolved":
            return False
        if not getattr(phase4, "profile_id", None):
            return False
        if not isinstance(getattr(phase4, "ai_template_hook", None), dict):
            return False
        diagnostics = list(getattr(phase4, "template_diagnostics", []) or [])
        return any(str(item).startswith("template_lookup:no_template_for_profile:") for item in diagnostics)

    @staticmethod
    def _sanitize_identifier(value: str, *, fallback: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
        return normalized or fallback

    def _build_pattern_generation_request(self, phase4) -> PatternGenerationRequest:
        hook = phase4.ai_template_hook
        if not isinstance(hook, dict):
            raise ValueError("missing ai_template_hook")
        profile_id = str(hook.get("profile_id") or phase4.profile_id or "").strip()
        if not profile_id:
            raise ValueError("missing profile_id")
        vendor_identity = str(hook.get("vendor_identity") or phase4.vendor_identity or phase4.sender_domain or "").strip()
        if not vendor_identity:
            raise ValueError("missing vendor_identity")
        body_text = str(hook.get("scrubbed_text") or "").strip()
        if not body_text:
            raise ValueError("missing scrubbed_text")
        template_root = self._sanitize_identifier(profile_id, fallback="order_template")
        vendor_root = self._sanitize_identifier(vendor_identity, fallback="generic")
        if not template_root.startswith(vendor_root):
            template_root = f"{vendor_root}_{template_root}"
        links = hook.get("extracted_links")
        links_json = links if isinstance(links, list) else []
        return PatternGenerationRequest(
            template_id=f"{template_root}.v1",
            profile_id=profile_id,
            template_version="v1",
            vendor_identity=vendor_identity,
            expected_label="ORDER",
            from_name=str(phase4.sender_name or vendor_identity).strip() or vendor_identity,
            from_email=str(phase4.sender_email or f"unknown@{vendor_root}.local").strip(),
            subject=str(phase4.subject or "").strip() or profile_id,
            received_at=datetime.now(UTC).isoformat(),
            body_text=body_text,
            body_html="",
            links_json=[item for item in links_json if isinstance(item, dict)],
        )

    @staticmethod
    def _build_shadow_comparison(phase4, evaluation) -> dict[str, object]:
        active_fields = {
            field_name: field.value
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
