from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field

from email_node.patterns import (
    PatternGenerationRequest,
    ProbationStore,
    ProbationTemplateState,
    TemplatePromotionService,
    build_action_required_ai_template_request,
)
from email_node.shared_pipeline_core import (
    SharedEmailPipelineCore,
    SharedOutputPersistenceHandler,
    SharedPolicyActionRouter,
    SharedActionGate,
    SharedTemplateExecutionEngine,
    SharedTemplateRegistry,
    build_probation_shadow_comparison,
    get_flow_family_config,
    load_action_routing_policy,
    load_profile_definition_pack,
    load_scrub_heuristic_pack,
    load_validation_policy,
)
from email_node.shared_pipeline_core.pipeline import SharedEmailPipelineHooks
from email_node.shared_pipeline_core.profile_detector import SharedProfileDetectorEngine
from email_node.shared_pipeline_core.probation import (
    SharedProbationEvaluator,
    SharedProbationMetrics,
    SharedProbationPromotionManager,
    SharedProbationPromotionPolicy,
)
from email_node.shared_pipeline_core.scrub_engine import SharedScrubEngine
from providers.gmail.order_template_registry import SUPPORTED_EXTRACTION_METHODS, SUPPORTED_TRANSFORMS
from providers.gmail.models import GmailPhase3ProfileCandidate, GmailPhase3WorkingEmail


SCRUBBER_VERSION = "action-required-phase2-scrubber.v1"
EXTRACTOR_VERSION = "action-required-phase4-extractor.v1"
TEMPLATE_SCHEMA_VERSION = "action-required-phase4-template.v1"


class ActionRequiredActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: bool
    blocked_reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class GmailActionRequiredPhase2Scrubber(SharedScrubEngine):
    def __init__(self) -> None:
        flow_config = get_flow_family_config("action_required")
        super().__init__(
            heuristic_pack=load_scrub_heuristic_pack(flow_config.scrub_heuristic_pack),
            scrubber_version=SCRUBBER_VERSION,
        )


class GmailActionRequiredPhase3ProfileDetector(SharedProfileDetectorEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        config = get_flow_family_config("action_required", runtime_dir=runtime_dir)
        profile_pack = load_profile_definition_pack(config.profile_detector_pack, runtime_dir=runtime_dir)
        super().__init__(
            taxonomy=profile_pack.taxonomy,
            taxonomy_version=profile_pack.taxonomy_version,
            known_vendor_identities=profile_pack.known_vendor_identities,
            rules=profile_pack.load_rules(),
        )

    def generate_candidates(
        self,
        working: GmailPhase3WorkingEmail,
    ) -> tuple[list[GmailPhase3ProfileCandidate], list[str]]:
        signals = self._signal_terms()
        subject = (working.subject or "").lower()
        text = working.scrubbed_text.lower()
        sender_domain = (working.sender_domain or "").lower()
        vendor = working.vendor_identity
        candidates: dict[str, list[str]] = {}

        def add(profile_id: str, reason: str) -> None:
            if profile_id in self.taxonomy:
                candidates.setdefault(profile_id, []).append(reason)

        signal_to_profile = {
            "subscription_expiring_terms": ("subscription_expiring", "subscription_expiring_language"),
            "benefit_order_update_terms": ("benefit_order_update_required", "benefit_order_update_language"),
            "appointment_preparation_terms": ("appointment_preparation_required", "appointment_preparation_language"),
            "appointment_scheduling_terms": ("appointment_scheduling_required", "appointment_scheduling_language"),
            "payment_due_terms": ("payment_due", "payment_due_language"),
            "payment_method_update_terms": ("payment_method_update_required", "payment_method_update_language"),
            "subscription_payment_failed_terms": ("subscription_payment_failed", "subscription_payment_failed_language"),
            "application_completion_terms": ("application_completion_required", "application_completion_language"),
            "account_verification_terms": ("account_verification_required", "account_verification_language"),
            "verification_code_terms": ("verification_code_required", "verification_code_language"),
            "account_retention_terms": ("account_retention_required", "account_retention_language"),
            "security_alert_terms": ("security_alert_action_required", "security_alert_language"),
            "site_issue_terms": ("site_issue_action_required", "site_issue_language"),
            "service_issue_terms": ("service_issue_action_required", "service_issue_language"),
            "document_signature_terms": ("document_signature_required", "document_signature_language"),
            "document_available_terms": ("document_available_action_required", "document_available_language"),
            "pickup_ready_action_terms": ("pickup_ready_action_required", "pickup_ready_action_language"),
            "travel_check_in_terms": ("travel_check_in_required", "travel_check_in_language"),
            "benefit_expiring_terms": ("benefit_expiring", "benefit_expiring_language"),
            "generic_action_terms": ("generic_action_required", "generic_action_language"),
        }
        for signal_key, (profile_id, reason) in signal_to_profile.items():
            terms = signals.get(signal_key, [])
            if terms and (self._contains_any(subject, terms) or self._contains_any(text, terms)):
                add(profile_id, reason)

        sender_domain_profiles = self.rules.get("sender_domain_profiles", {})
        if isinstance(sender_domain_profiles, dict):
            mapped_profile = sender_domain_profiles.get(sender_domain)
            if isinstance(mapped_profile, str):
                add(mapped_profile, f"sender_domain:{sender_domain.replace('.', '_')}")

        diagnostics: list[str] = []
        candidate_models: list[GmailPhase3ProfileCandidate] = []
        for profile_id, reasons in candidates.items():
            taxonomy = self.taxonomy[profile_id]
            diagnostics.append(f"candidate:{profile_id} reasons={','.join(reasons)}")
            candidate_models.append(
                GmailPhase3ProfileCandidate(
                    profile_id=profile_id,
                    profile_family=str(taxonomy["profile_family"]),
                    profile_subtype=str(taxonomy["profile_subtype"]),
                    vendor_identity=(str(taxonomy["vendor_identity"]) if taxonomy["vendor_identity"] else vendor),
                    sender_identity=working.sender_identity,
                    reasons=reasons,
                )
            )

        if not candidate_models:
            diagnostics.append("candidate_generation:no_candidates")
        return candidate_models, diagnostics

    def score_candidates(
        self,
        working: GmailPhase3WorkingEmail,
        candidates: list[GmailPhase3ProfileCandidate],
    ) -> tuple[list[GmailPhase3ProfileCandidate], list[str]]:
        signals = self._signal_terms()
        weights = self._weights()
        thresholds = self._thresholds()
        diagnostics: list[str] = []
        ranked: list[GmailPhase3ProfileCandidate] = []
        subject = (working.subject or "").lower()
        text = working.scrubbed_text.lower()
        vendor = working.vendor_identity

        profile_rules = {
            "subscription_expiring": ("subscription_expiring_terms", "subscription_expiring_language"),
            "benefit_order_update_required": ("benefit_order_update_terms", "benefit_order_update_language"),
            "appointment_preparation_required": ("appointment_preparation_terms", "appointment_preparation_language"),
            "appointment_scheduling_required": ("appointment_scheduling_terms", "appointment_scheduling_language"),
            "payment_due": ("payment_due_terms", "payment_due_language"),
            "payment_method_update_required": ("payment_method_update_terms", "payment_method_update_language"),
            "subscription_payment_failed": ("subscription_payment_failed_terms", "subscription_payment_failed_language"),
            "application_completion_required": ("application_completion_terms", "application_completion_language"),
            "account_verification_required": ("account_verification_terms", "account_verification_language"),
            "verification_code_required": ("verification_code_terms", "verification_code_language"),
            "account_retention_required": ("account_retention_terms", "account_retention_language"),
            "security_alert_action_required": ("security_alert_terms", "security_alert_language"),
            "site_issue_action_required": ("site_issue_terms", "site_issue_language"),
            "service_issue_action_required": ("service_issue_terms", "service_issue_language"),
            "document_signature_required": ("document_signature_terms", "document_signature_language"),
            "document_available_action_required": ("document_available_terms", "document_available_language"),
            "pickup_ready_action_required": ("pickup_ready_action_terms", "pickup_ready_action_language"),
            "travel_check_in_required": ("travel_check_in_terms", "travel_check_in_language"),
            "benefit_expiring": ("benefit_expiring_terms", "benefit_expiring_language"),
            "generic_action_required": ("generic_action_terms", "generic_action_language"),
        }

        for candidate in candidates:
            score = 0
            reasons = list(candidate.reasons)
            if candidate.vendor_identity and candidate.vendor_identity == vendor:
                score += weights.get("sender_match", 0)
                reasons.append("score:sender_match")

            signal_key, weight_key = profile_rules.get(candidate.profile_id, ("", ""))
            terms = signals.get(signal_key, [])
            if terms and (self._contains_any(subject, terms) or self._contains_any(text, terms)):
                score += weights.get(weight_key, 0)
                reasons.append(f"score:{weight_key}")

            confidence_level = "high" if score >= thresholds.get("high_score", 14) else "medium" if score >= thresholds.get("medium_score", 8) else "low"
            ranked.append(candidate.model_copy(update={"score": score, "confidence_level": confidence_level, "reasons": reasons}))
            diagnostics.append(f"scored:{candidate.profile_id} score={score} reasons={','.join(reasons[-5:])}")

        ranked.sort(key=lambda item: (item.score, len(item.reasons)), reverse=True)
        return ranked, diagnostics


class GmailActionRequiredTemplateRegistry(SharedTemplateRegistry):
    def __init__(self, base_dir: Path | None = None) -> None:
        template_dir = base_dir or get_flow_family_config("action_required").template_dir
        super().__init__(
            base_dir=template_dir,
            fallback_dirs=[],
            schema_version=TEMPLATE_SCHEMA_VERSION,
            supported_extraction_methods=SUPPORTED_EXTRACTION_METHODS,
            supported_transforms=SUPPORTED_TRANSFORMS,
        )


class GmailActionRequiredPhase4Extractor(SharedTemplateExecutionEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        flow_config = get_flow_family_config("action_required", runtime_dir=runtime_dir)
        super().__init__(
            registry=GmailActionRequiredTemplateRegistry(flow_config.template_dir),
            extractor_version=EXTRACTOR_VERSION,
            template_schema_version=TEMPLATE_SCHEMA_VERSION,
            validation_policy=load_validation_policy(flow_config.validation_policy),
        )

    def build_ai_template_hook(self, phase3) -> dict[str, object]:
        phase2 = phase3.phase2_reference
        return {
            "sender_identity": phase3.sender_identity,
            "vendor_identity": phase3.vendor_identity or phase3.sender_domain,
            "profile_id": phase3.profile_id,
            "profile_family": phase3.profile_family,
            "profile_subtype": phase3.profile_subtype,
            "subject": phase3.subject,
            "scrubbed_text": phase2.scrubbed_text,
            "normalized_lines": list(phase2.normalized_lines),
            "extracted_links": [
                link.model_dump() if hasattr(link, "model_dump") else dict(link)
                for link in phase2.extracted_links
            ],
            "expected_output_schema": {
                "template_id": "candidate_template_id",
                "profile_id": phase3.profile_id,
                "template_version": "v1",
                "enabled": True,
                "match": {},
                "extract": {},
                "required_fields": [],
                "confidence_rules": {},
                "post_process": {},
            },
        }


class ActionRequiredFlowRuntime:
    flow_family = "action_required"

    def __init__(
        self,
        *,
        phase2_scrubber: GmailActionRequiredPhase2Scrubber | None = None,
        phase3_detector: GmailActionRequiredPhase3ProfileDetector | None = None,
        phase4_extractor: GmailActionRequiredPhase4Extractor | None = None,
        probation_store: ProbationStore | None = None,
        probation_evaluator: SharedProbationEvaluator | None = None,
        probation_promotion: SharedProbationPromotionManager | None = None,
        generate_probation_template: Callable[[PatternGenerationRequest], Awaitable[dict[str, object]]] | None = None,
        ai_calls_enabled: Callable[[], bool] | None = None,
        runtime_dir: Path | None = None,
    ) -> None:
        self.flow_config = get_flow_family_config("action_required", runtime_dir=runtime_dir)
        self.phase2_scrubber = phase2_scrubber or GmailActionRequiredPhase2Scrubber()
        self.phase3_detector = phase3_detector or GmailActionRequiredPhase3ProfileDetector(runtime_dir=runtime_dir)
        self.phase4_extractor = phase4_extractor or GmailActionRequiredPhase4Extractor(runtime_dir=runtime_dir)
        self.probation_store = probation_store or ProbationStore(runtime_dir=runtime_dir, flow_family="action_required")
        self.probation_evaluator = probation_evaluator or SharedProbationEvaluator(
            probation_store=self.probation_store,
            extractor=self.phase4_extractor,
        )
        self.probation_promotion = probation_promotion or SharedProbationPromotionManager(
            promotion_service=TemplatePromotionService(
                probation_store=self.probation_store,
                active_dir=self.flow_config.template_dir,
            ),
            policy=SharedProbationPromotionPolicy(),
        )
        self.generate_probation_template = generate_probation_template
        self.ai_calls_enabled = ai_calls_enabled or (lambda: True)
        self.decision_engine = None
        self.output_handler = SharedOutputPersistenceHandler(flow_family="action_required", runtime_dir=runtime_dir)
        self.action_gate = SharedActionGate()
        self.action_router = SharedPolicyActionRouter(
            policy=load_action_routing_policy(self.flow_config.action_router_policy)
        )
        self.shared_core = SharedEmailPipelineCore(
            flow_config=self.flow_config,
            hooks=SharedEmailPipelineHooks(
                scrub=self.phase2_scrubber.scrub,
                detect_profile=self.phase3_detector.detect,
                extract_template=self.phase4_extractor.extract,
                attach_probation_template=self.attach_probation_template,
                run_probation_shadow_mode=self.run_probation_shadow_mode,
                decide=self._decide,
                persist=lambda decision, phase4: self.output_handler.persist(decision=decision, phase4=phase4),
                authorize_actions=lambda decision, phase4: self.action_gate.authorize(decision=decision, phase4=phase4),
                route_actions=lambda decision, authorization, phase4: self.action_router.route(
                    decision=decision,
                    authorization=authorization,
                    phase4=phase4,
                ),
                write_order_record=self.write_action_record,
                build_user_notification=self.build_user_notification,
                build_tracking_monitor=self.build_followup_action,
            ),
        )
        from email_node.shared_pipeline_core import load_decision_policy
        from email_node.shared_pipeline_core.decision import SharedDecisionEngine

        self.decision_engine = SharedDecisionEngine(policy=load_decision_policy(self.flow_config.decision_policy))

    async def process_normalized_email(self, normalized) -> dict[str, object]:
        return await self.shared_core.process_normalized_email(normalized)

    async def attach_probation_template(self, phase4):
        if not self._should_attempt_probation(phase4):
            return phase4
        profile_id = str(getattr(phase4, "profile_id", "") or "").strip()
        vendor_identity = str(
            getattr(phase4, "vendor_identity", None)
            or getattr(phase4, "sender_domain", None)
            or ""
        ).strip().lower()
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
        if self.generate_probation_template is None:
            return phase4.model_copy(
                update={
                    "template_diagnostics": list(phase4.template_diagnostics)
                    + ["probation_template:skipped_no_generator"]
                }
            )
        try:
            request = build_action_required_ai_template_request(phase4)
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
        return phase4

    def run_probation_shadow_mode(self, phase4):
        if not getattr(phase4, "template_id", None):
            return phase4
        probation_state = self.probation_store.find_state(
            profile_id=str(getattr(phase4, "profile_id", "") or "").strip() or None,
            vendor_identity=str(
                getattr(phase4, "vendor_identity", None)
                or getattr(phase4, "sender_domain", None)
                or ""
            ).strip().lower()
            or None,
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
        return phase4

    def _decide(self, phase4):
        return self.decision_engine.decide(phase4)

    @staticmethod
    def write_action_record(decision, phase4, action_routing) -> ActionRequiredActionResult:
        if "store_action_record" not in action_routing.action_intents:
            return ActionRequiredActionResult(
                queued=False,
                blocked_reason="no_action_record_intent",
                diagnostics=list(action_routing.diagnostics) + ["action_required_record:skipped:no_action_record_intent"],
            )
        return ActionRequiredActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["action_required_record:queued"],
        )

    @staticmethod
    def build_user_notification(decision, action_routing, phase4) -> ActionRequiredActionResult:
        if "user_notification" not in action_routing.action_intents:
            return ActionRequiredActionResult(
                queued=False,
                blocked_reason="no_user_notification_intent",
                diagnostics=list(action_routing.diagnostics) + ["action_required_notification:skipped:no_user_notification_intent"],
            )
        return ActionRequiredActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["action_required_notification:queued"],
        )

    @staticmethod
    def build_followup_action(decision, action_routing, phase4) -> ActionRequiredActionResult:
        followup_intents = {"queue_reminder", "mark_high_priority", "mark_for_manual_review"}
        selected = [intent for intent in action_routing.action_intents if intent in followup_intents]
        if not selected:
            return ActionRequiredActionResult(
                queued=False,
                blocked_reason="no_followup_intent",
                diagnostics=list(action_routing.diagnostics) + ["action_required_followup:skipped:no_followup_intent"],
            )
        return ActionRequiredActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + [f"action_required_followup:queued:{','.join(selected)}"],
        )

    @staticmethod
    def _should_attempt_probation(phase4) -> bool:
        extraction_status = str(getattr(phase4, "extraction_status", "") or "")
        return extraction_status in {"failed", "unresolved"}

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
