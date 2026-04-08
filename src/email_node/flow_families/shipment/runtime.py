from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field

from email_node.flow_families.shared_probation_runtime import SharedFamilyProbationRuntimeMixin
from email_node.patterns import (
    PatternGenerationRequest,
    ProbationStore,
    TemplatePromotionService,
    build_family_ai_template_request,
)
from email_node.shared_pipeline_core import (
    SharedActionGate,
    SharedEmailPipelineCore,
    SharedOutputPersistenceHandler,
    SharedPolicyActionRouter,
    SharedTemplateExecutionEngine,
    SharedTemplateRegistry,
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
    SharedProbationPromotionManager,
    SharedProbationPromotionPolicy,
)
from email_node.shared_pipeline_core.scrub_engine import SharedScrubEngine
from providers.gmail.models import GmailPhase3ProfileCandidate, GmailPhase3WorkingEmail
from providers.gmail.order_template_registry import SUPPORTED_EXTRACTION_METHODS, SUPPORTED_TRANSFORMS


SCRUBBER_VERSION = "shipment-phase2-scrubber.v1"
EXTRACTOR_VERSION = "shipment-phase4-extractor.v1"
TEMPLATE_SCHEMA_VERSION = "shipment-phase4-template.v1"


class ShipmentActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: bool
    blocked_reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class GmailShipmentPhase2Scrubber(SharedScrubEngine):
    def __init__(self) -> None:
        flow_config = get_flow_family_config("shipment")
        super().__init__(
            heuristic_pack=load_scrub_heuristic_pack(flow_config.scrub_heuristic_pack),
            scrubber_version=SCRUBBER_VERSION,
        )


class GmailShipmentPhase3ProfileDetector(SharedProfileDetectorEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        config = get_flow_family_config("shipment", runtime_dir=runtime_dir)
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
            "shipped_terms": ("shipped", "shipped_language"),
            "out_for_delivery_terms": ("out_for_delivery", "out_for_delivery_language"),
            "delivered_terms": ("delivered", "delivered_language"),
            "delayed_terms": ("delayed", "delayed_language"),
            "label_created_terms": ("label_created", "label_created_language"),
            "generic_shipment_terms": ("generic_shipment_update", "generic_shipment_language"),
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
            "shipped": ("shipped_terms", "shipped_language"),
            "out_for_delivery": ("out_for_delivery_terms", "out_for_delivery_language"),
            "delivered": ("delivered_terms", "delivered_language"),
            "delayed": ("delayed_terms", "delayed_language"),
            "label_created": ("label_created_terms", "label_created_language"),
            "generic_shipment_update": ("generic_shipment_terms", "generic_shipment_language"),
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

            confidence_level = (
                "high"
                if score >= thresholds.get("high_score", 14)
                else "medium"
                if score >= thresholds.get("medium_score", 8)
                else "low"
            )
            ranked.append(
                candidate.model_copy(
                    update={"score": score, "confidence_level": confidence_level, "reasons": reasons}
                )
            )
            diagnostics.append(f"scored:{candidate.profile_id} score={score} reasons={','.join(reasons[-5:])}")

        ranked.sort(key=lambda item: (item.score, len(item.reasons)), reverse=True)
        if not ranked:
            diagnostics.append("candidate_scoring:no_candidates")
        return ranked, diagnostics


class GmailShipmentTemplateRegistry(SharedTemplateRegistry):
    def __init__(self, base_dir: Path | None = None) -> None:
        template_dir = base_dir or get_flow_family_config("shipment").template_dir
        super().__init__(
            base_dir=template_dir,
            fallback_dirs=[],
            schema_version=TEMPLATE_SCHEMA_VERSION,
            supported_extraction_methods=SUPPORTED_EXTRACTION_METHODS,
            supported_transforms=SUPPORTED_TRANSFORMS,
        )


class GmailShipmentPhase4Extractor(SharedTemplateExecutionEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        flow_config = get_flow_family_config("shipment", runtime_dir=runtime_dir)
        super().__init__(
            registry=GmailShipmentTemplateRegistry(flow_config.template_dir),
            extractor_version=EXTRACTOR_VERSION,
            template_schema_version=TEMPLATE_SCHEMA_VERSION,
            validation_policy=load_validation_policy(flow_config.validation_policy),
        )


class ShipmentFlowRuntime(SharedFamilyProbationRuntimeMixin):
    flow_family = "shipment"

    def __init__(
        self,
        *,
        phase2_scrubber: GmailShipmentPhase2Scrubber | None = None,
        phase3_detector: GmailShipmentPhase3ProfileDetector | None = None,
        phase4_extractor: GmailShipmentPhase4Extractor | None = None,
        probation_store: ProbationStore | None = None,
        probation_evaluator: SharedProbationEvaluator | None = None,
        probation_promotion: SharedProbationPromotionManager | None = None,
        generate_probation_template: Callable[[PatternGenerationRequest], Awaitable[dict[str, object]]] | None = None,
        ai_calls_enabled: Callable[[], bool] | None = None,
        runtime_dir: Path | None = None,
    ) -> None:
        self.flow_config = get_flow_family_config("shipment", runtime_dir=runtime_dir)
        self.phase2_scrubber = phase2_scrubber or GmailShipmentPhase2Scrubber()
        self.phase3_detector = phase3_detector or GmailShipmentPhase3ProfileDetector(runtime_dir=runtime_dir)
        self.phase4_extractor = phase4_extractor or GmailShipmentPhase4Extractor(runtime_dir=runtime_dir)
        self.probation_store = probation_store or ProbationStore(runtime_dir=runtime_dir, flow_family="shipment")
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
        self.decision_engine = self._build_decision_engine()
        self.output_handler = SharedOutputPersistenceHandler(flow_family="shipment", runtime_dir=runtime_dir)
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
                decide=self.decision_engine.decide,
                persist=lambda decision, phase4: self.output_handler.persist(decision=decision, phase4=phase4),
                authorize_actions=lambda decision, phase4: self.action_gate.authorize(decision=decision, phase4=phase4),
                route_actions=lambda decision, authorization, phase4: self.action_router.route(
                    decision=decision,
                    authorization=authorization,
                    phase4=phase4,
                ),
                write_order_record=self.write_shipment_record,
                build_user_notification=self.build_user_notification,
                build_tracking_monitor=self.build_followup_action,
            ),
        )

    async def process_normalized_email(self, normalized) -> dict[str, object]:
        return await self.shared_core.process_normalized_email(normalized)

    def _build_probation_request(self, phase4) -> PatternGenerationRequest:
        return build_family_ai_template_request(
            phase4,
            expected_label="SHIPMENT",
            fallback_template_root="shipment",
        )

    @staticmethod
    def write_shipment_record(decision, phase4, action_routing) -> ShipmentActionResult:
        if "store_shipment_record" not in action_routing.action_intents:
            return ShipmentActionResult(
                queued=False,
                blocked_reason="no_shipment_record_intent",
                diagnostics=list(action_routing.diagnostics) + ["shipment_record:skipped:no_shipment_record_intent"],
            )
        return ShipmentActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["shipment_record:queued"],
        )

    @staticmethod
    def build_user_notification(decision, action_routing, phase4) -> ShipmentActionResult:
        if "user_notification" not in action_routing.action_intents:
            return ShipmentActionResult(
                queued=False,
                blocked_reason="no_user_notification_intent",
                diagnostics=list(action_routing.diagnostics) + ["shipment_notification:skipped:no_user_notification_intent"],
            )
        return ShipmentActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["shipment_notification:queued"],
        )

    @staticmethod
    def build_followup_action(decision, action_routing, phase4) -> ShipmentActionResult:
        followup_intents = {"mark_for_manual_review"}
        selected = [intent for intent in action_routing.action_intents if intent in followup_intents]
        if not selected:
            return ShipmentActionResult(
                queued=False,
                blocked_reason="no_followup_intent",
                diagnostics=list(action_routing.diagnostics) + ["shipment_followup:skipped:no_followup_intent"],
            )
        return ShipmentActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + [f"shipment_followup:queued:{','.join(selected)}"],
        )

    def _build_decision_engine(self):
        from email_node.shared_pipeline_core.decision import SharedDecisionEngine
        from email_node.flow_families.shipment.decision import build_decision_policy

        return SharedDecisionEngine(policy=build_decision_policy())
