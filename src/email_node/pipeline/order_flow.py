from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Awaitable, Callable

from email_node.actions.tracking_monitor_handler import TrackingMonitorHandler
from email_node.actions.user_notification_handler import UserNotificationHandler
from email_node.orders.order_record_service import OrderRecordService
from email_node.pipeline.order_action_gate import OrderActionGate
from email_node.pipeline.order_action_router import OrderActionRouter
from email_node.pipeline.order_decision_engine import OrderDecisionEngine
from email_node.pipeline.order_output_handler import OrderOutputHandler
from email_node.patterns import PatternGenerationRequest, build_order_ai_template_request
from email_node.patterns.probation_evaluator import ProbationEvaluator
from email_node.patterns.probation_metrics import ProbationMetrics
from email_node.patterns.probation_policy import ProbationPromotionPolicy
from email_node.patterns.probation_promotion import ProbationPromotionManager
from email_node.patterns.probation_state import ProbationTemplateState
from email_node.patterns.probation_store import ProbationStore
from email_node.shared_pipeline_core import SharedEmailPipelineCore, build_probation_shadow_comparison, get_flow_family_config
from email_node.shared_pipeline_core.pipeline import SharedEmailPipelineHooks
from email_node.patterns.template_promotion_service import TemplatePromotionService
from logging_utils import get_logger
from providers.gmail.order_phase2 import GmailOrderPhase2Scrubber
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


LOGGER = get_logger(__name__)


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
        order_checks_enabled: Callable[[], bool] | None = None,
        decision_engine: OrderDecisionEngine | None = None,
        output_handler: OrderOutputHandler | None = None,
        action_gate: OrderActionGate | None = None,
        action_router: OrderActionRouter | None = None,
        order_record_service: OrderRecordService | None = None,
        user_notification_handler: UserNotificationHandler | None = None,
        tracking_monitor_handler: TrackingMonitorHandler | None = None,
        runtime_dir: Path | None = None,
    ) -> None:
        self.flow_config = get_flow_family_config("order", runtime_dir=runtime_dir)
        self.phase2_scrubber = phase2_scrubber or GmailOrderPhase2Scrubber()
        self.phase3_detector = phase3_detector or GmailOrderPhase3ProfileDetector()
        self.phase4_extractor = phase4_extractor or GmailOrderPhase4Extractor()
        self.probation_store = probation_store or ProbationStore(runtime_dir=runtime_dir, flow_family="order")
        self.probation_evaluator = probation_evaluator or ProbationEvaluator(probation_store=self.probation_store)
        self.probation_promotion = probation_promotion or ProbationPromotionManager(
            promotion_service=TemplatePromotionService(
                probation_store=self.probation_store,
                active_dir=self.flow_config.template_dir,
            ),
            policy=ProbationPromotionPolicy(),
        )
        self.generate_probation_template = generate_probation_template
        self.ai_calls_enabled = ai_calls_enabled or (lambda: True)
        self.order_checks_enabled = order_checks_enabled or (lambda: True)
        self.decision_engine = decision_engine or OrderDecisionEngine()
        self.output_handler = output_handler or OrderOutputHandler(runtime_dir)
        self.action_gate = action_gate or OrderActionGate()
        self.action_router = action_router or OrderActionRouter()
        self.order_record_service = order_record_service or OrderRecordService(runtime_dir)
        self.user_notification_handler = user_notification_handler or UserNotificationHandler()
        self.tracking_monitor_handler = tracking_monitor_handler or TrackingMonitorHandler()
        self.shared_core = SharedEmailPipelineCore(
            flow_config=self.flow_config,
            hooks=SharedEmailPipelineHooks(
                scrub=self.phase2_scrubber.scrub,
                detect_profile=self.phase3_detector.detect,
                extract_template=self.phase4_extractor.extract,
                attach_probation_template=self.attach_probation_template,
                run_probation_shadow_mode=self._run_probation_shadow_mode,
                decide=self.decision_engine.decide,
                persist=lambda decision, phase4: self.output_handler.persist(decision=decision, phase4=phase4),
                authorize_actions=lambda decision, phase4: self.action_gate.authorize(decision=decision, phase4=phase4),
                route_actions=lambda decision, authorization, phase4: self.action_router.route(
                    decision=decision,
                    authorization=authorization,
                    phase4=phase4,
                ),
                write_order_record=lambda decision, phase4, action_routing: self.order_record_service.write_from_order_result(
                    decision=decision,
                    phase4=phase4,
                    action_routing=action_routing,
                ),
                build_user_notification=lambda decision, action_routing, phase4: self.user_notification_handler.build_request(
                    decision=decision,
                    action_routing=action_routing,
                    phase4=phase4,
                ),
                build_tracking_monitor=lambda decision, action_routing, phase4: self.tracking_monitor_handler.build_request(
                    decision=decision,
                    action_routing=action_routing,
                    phase4=phase4,
                ),
            ),
        )

    async def process_normalized_email(self, normalized) -> dict[str, object]:
        return await self.shared_core.process_normalized_email(normalized)

    async def attach_probation_template(self, phase4):
        if not self._should_attempt_probation(phase4):
            return phase4
        probation_profile_id = self._probation_profile_id(phase4)
        probation_vendor_identity = self._probation_vendor_identity(phase4)
        existing_state = self.probation_store.find_state(
            profile_id=probation_profile_id,
            vendor_identity=probation_vendor_identity,
            status="probation",
        )
        if existing_state is not None:
            evaluation = self.probation_evaluator.evaluate(
                self._phase3_with_probation_profile(phase4, template_id=existing_state.template_id),
                template_id=existing_state.template_id,
            )
            updated_state = ProbationMetrics.update_state(existing_state, evaluation)
            updated_state = updated_state.model_copy(
                update={
                    "last_generation_attempt_at": datetime.now(UTC),
                    "last_generation_result": "skipped_existing_probation",
                }
            )
            updated_state = self.probation_promotion.evaluate_and_apply(updated_state)
            self.probation_store.save_state(updated_state)
            LOGGER.info(
                "Probation template evaluated",
                extra={
                    "event_data": {
                        "template_id": existing_state.template_id,
                        "message_id": phase4.message_id,
                        "hard_failure": evaluation.hard_failure,
                        "sample_count": updated_state.sample_count,
                        "status": updated_state.status,
                    }
                },
            )
            promotion_suffix = updated_state.status
            updated_phase4 = phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [
                        f"probation_template:existing:{existing_state.template_id}",
                        f"probation_template:evaluated:{existing_state.template_id}:{'hard_failure' if evaluation.hard_failure else 'ok'}",
                        f"probation_template:state:{existing_state.template_id}:{promotion_suffix}",
                    ]
                }
            )
            if evaluation.extraction_succeeded and evaluation.extracted_fields:
                updated_phase4 = self._apply_probation_template(updated_phase4, template_id=existing_state.template_id)
            return updated_phase4
        if not self.order_checks_enabled():
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics) + ["order_checks:disabled"]
                }
            )
        if not self.ai_calls_enabled():
            LOGGER.info(
                "Probation template generation skipped because AI calls are disabled",
                extra={"event_data": {"message_id": phase4.message_id, "profile_id": phase4.profile_id}},
            )
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
            request = build_order_ai_template_request(phase4)
        except ValueError as exc:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + [f"probation_template:request_build_failed:{exc}"]
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
            last_generation_attempt_at=now,
            last_generation_result="created",
            promotion_eligible=False,
            promotion_reason="Awaiting probation evaluation.",
        )
        self.probation_store.save_state(state)
        LOGGER.info(
            "Probation template created",
            extra={
                "event_data": {
                    "template_id": template_id,
                    "message_id": phase4.message_id,
                    "profile_id": request.profile_id,
                    "vendor_identity": request.vendor_identity,
                }
            },
        )
        return phase4.model_copy(
            update={
                "template_diagnostics": list(phase4.template_diagnostics) + [f"probation_template:created:{template_id}"]
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

    def _run_probation_shadow_mode(self, phase4):
        if not getattr(phase4, "template_id", None):
            return phase4
        probation_state = self.probation_store.find_state(
            profile_id=self._probation_profile_id(phase4),
            vendor_identity=self._probation_vendor_identity(phase4),
            status="probation",
        )
        if probation_state is None:
            return phase4
        evaluation = self.probation_evaluator.evaluate(
            self._phase3_with_probation_profile(phase4, template_id=probation_state.template_id),
            template_id=probation_state.template_id,
        )
        updated_state = ProbationMetrics.update_state(probation_state, evaluation)
        updated_state = self.probation_promotion.evaluate_and_apply(updated_state)
        self.probation_store.save_state(updated_state)
        comparison = build_probation_shadow_comparison(phase4, evaluation)
        self.probation_store.save_shadow_comparison(probation_state.template_id, phase4.message_id, comparison)
        LOGGER.info(
            "Probation template shadow evaluation completed",
            extra={
                "event_data": {
                    "template_id": probation_state.template_id,
                    "message_id": phase4.message_id,
                    "active_template_id": phase4.template_id,
                    "status": updated_state.status,
                }
            },
        )
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
        if getattr(phase4, "extraction_status", None) not in {"unresolved", "failed"}:
            return False
        hook = getattr(phase4, "ai_template_hook", None)
        if not isinstance(hook, dict):
            return False
        if not (getattr(phase4, "profile_id", None) or hook.get("profile_id")):
            return False
        diagnostics = list(getattr(phase4, "template_diagnostics", []) or [])
        return any(
            str(item).startswith("template_lookup:no_template_for_profile:") or str(item) == "phase3 profile_id is missing"
            for item in diagnostics
        )

    @staticmethod
    def _probation_profile_id(phase4) -> str | None:
        hook = getattr(phase4, "ai_template_hook", None)
        if isinstance(hook, dict):
            profile_id = str(hook.get("profile_id") or "").strip()
            if profile_id:
                return profile_id
        profile_id = str(getattr(phase4, "profile_id", "") or "").strip()
        return profile_id or None

    @staticmethod
    def _probation_vendor_identity(phase4) -> str | None:
        hook = getattr(phase4, "ai_template_hook", None)
        if isinstance(hook, dict):
            vendor_identity = str(hook.get("vendor_identity") or "").strip()
            if vendor_identity:
                return vendor_identity
        vendor_identity = str(getattr(phase4, "vendor_identity", "") or "").strip()
        return vendor_identity or None

    def _phase3_with_probation_profile(self, phase4, *, template_id: str | None = None):
        phase3 = phase4.phase3_reference
        hook = getattr(phase4, "ai_template_hook", None)
        if not isinstance(hook, dict):
            return phase3
        profile_id = self._probation_profile_id(phase4)
        if not profile_id or getattr(phase3, "profile_id", None):
            return phase3
        profile_family = str(hook.get("profile_family") or "order").strip() or "order"
        profile_subtype = str(hook.get("profile_subtype") or "confirmation").strip() or "confirmation"
        diagnostics = list(getattr(phase3, "profile_diagnostics", []) or [])
        diagnostics.append(f"probation_profile_fallback:{profile_id}")
        if template_id:
            diagnostics.append(f"probation_profile_template:{template_id}")
        return phase3.model_copy(
            update={
                "profile_id": profile_id,
                "profile_family": profile_family,
                "profile_subtype": profile_subtype,
                "profile_status": "partial",
                "profile_diagnostics": diagnostics,
            }
        )
