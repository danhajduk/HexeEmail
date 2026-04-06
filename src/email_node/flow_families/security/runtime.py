from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

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
from email_node.shared_pipeline_core.scrub_engine import SharedScrubEngine
from providers.gmail.models import GmailPhase3ProfileCandidate, GmailPhase3WorkingEmail
from providers.gmail.order_template_registry import SUPPORTED_EXTRACTION_METHODS, SUPPORTED_TRANSFORMS


SCRUBBER_VERSION = "security-phase2-scrubber.v1"
EXTRACTOR_VERSION = "security-phase4-extractor.v1"
TEMPLATE_SCHEMA_VERSION = "security-phase4-template.v1"


class SecurityActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: bool
    blocked_reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class GmailSecurityPhase2Scrubber(SharedScrubEngine):
    def __init__(self) -> None:
        flow_config = get_flow_family_config("security")
        super().__init__(
            heuristic_pack=load_scrub_heuristic_pack(flow_config.scrub_heuristic_pack),
            scrubber_version=SCRUBBER_VERSION,
        )


class GmailSecurityPhase3ProfileDetector(SharedProfileDetectorEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        config = get_flow_family_config("security", runtime_dir=runtime_dir)
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
        return [], ["candidate_generation:no_candidates"]

    def score_candidates(
        self,
        working: GmailPhase3WorkingEmail,
        candidates: list[GmailPhase3ProfileCandidate],
    ) -> tuple[list[GmailPhase3ProfileCandidate], list[str]]:
        return [], ["candidate_scoring:no_candidates"]


class GmailSecurityTemplateRegistry(SharedTemplateRegistry):
    def __init__(self, base_dir: Path | None = None) -> None:
        template_dir = base_dir or get_flow_family_config("security").template_dir
        super().__init__(
            base_dir=template_dir,
            fallback_dirs=[],
            schema_version=TEMPLATE_SCHEMA_VERSION,
            supported_extraction_methods=SUPPORTED_EXTRACTION_METHODS,
            supported_transforms=SUPPORTED_TRANSFORMS,
        )


class GmailSecurityPhase4Extractor(SharedTemplateExecutionEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        flow_config = get_flow_family_config("security", runtime_dir=runtime_dir)
        super().__init__(
            registry=GmailSecurityTemplateRegistry(flow_config.template_dir),
            extractor_version=EXTRACTOR_VERSION,
            template_schema_version=TEMPLATE_SCHEMA_VERSION,
            validation_policy=load_validation_policy(flow_config.validation_policy),
        )


class SecurityFlowRuntime:
    flow_family = "security"

    def __init__(
        self,
        *,
        phase2_scrubber: GmailSecurityPhase2Scrubber | None = None,
        phase3_detector: GmailSecurityPhase3ProfileDetector | None = None,
        phase4_extractor: GmailSecurityPhase4Extractor | None = None,
        runtime_dir: Path | None = None,
    ) -> None:
        self.flow_config = get_flow_family_config("security", runtime_dir=runtime_dir)
        self.phase2_scrubber = phase2_scrubber or GmailSecurityPhase2Scrubber()
        self.phase3_detector = phase3_detector or GmailSecurityPhase3ProfileDetector(runtime_dir=runtime_dir)
        self.phase4_extractor = phase4_extractor or GmailSecurityPhase4Extractor(runtime_dir=runtime_dir)
        self.decision_engine = self._build_decision_engine()
        self.output_handler = SharedOutputPersistenceHandler(flow_family="security", runtime_dir=runtime_dir)
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
                write_order_record=self.write_security_record,
                build_user_notification=self.build_user_notification,
                build_tracking_monitor=self.build_followup_action,
            ),
        )

    async def process_normalized_email(self, normalized) -> dict[str, object]:
        return await self.shared_core.process_normalized_email(normalized)

    @staticmethod
    async def attach_probation_template(phase4):
        return phase4

    @staticmethod
    def run_probation_shadow_mode(phase4):
        return phase4

    @staticmethod
    def write_security_record(decision, phase4, action_routing) -> SecurityActionResult:
        if "store_security_record" not in action_routing.action_intents:
            return SecurityActionResult(
                queued=False,
                blocked_reason="no_security_record_intent",
                diagnostics=list(action_routing.diagnostics) + ["security_record:skipped:no_security_record_intent"],
            )
        return SecurityActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["security_record:queued"],
        )

    @staticmethod
    def build_user_notification(decision, action_routing, phase4) -> SecurityActionResult:
        if "user_notification" not in action_routing.action_intents:
            return SecurityActionResult(
                queued=False,
                blocked_reason="no_user_notification_intent",
                diagnostics=list(action_routing.diagnostics) + ["security_notification:skipped:no_user_notification_intent"],
            )
        return SecurityActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["security_notification:queued"],
        )

    @staticmethod
    def build_followup_action(decision, action_routing, phase4) -> SecurityActionResult:
        followup_intents = {"mark_for_manual_review"}
        selected = [intent for intent in action_routing.action_intents if intent in followup_intents]
        if not selected:
            return SecurityActionResult(
                queued=False,
                blocked_reason="no_followup_intent",
                diagnostics=list(action_routing.diagnostics) + ["security_followup:skipped:no_followup_intent"],
            )
        return SecurityActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + [f"security_followup:queued:{','.join(selected)}"],
        )

    def _build_decision_engine(self):
        from email_node.shared_pipeline_core.decision import SharedDecisionEngine
        from email_node.flow_families.security.decision import build_decision_policy

        return SharedDecisionEngine(policy=build_decision_policy())
