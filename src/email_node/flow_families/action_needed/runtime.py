from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from email_node.shared_pipeline_core import (
    SharedEmailPipelineCore,
    SharedOutputPersistenceHandler,
    SharedPolicyActionRouter,
    SharedActionGate,
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
from providers.gmail.order_template_registry import SUPPORTED_EXTRACTION_METHODS, SUPPORTED_TRANSFORMS


SCRUBBER_VERSION = "action-needed-phase2-scrubber.v1"
EXTRACTOR_VERSION = "action-needed-phase4-extractor.v1"
TEMPLATE_SCHEMA_VERSION = "action-needed-phase4-template.v1"


class ActionNeededActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: bool
    blocked_reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class GmailActionNeededPhase2Scrubber(SharedScrubEngine):
    def __init__(self) -> None:
        flow_config = get_flow_family_config("action_needed")
        super().__init__(
            heuristic_pack=load_scrub_heuristic_pack(flow_config.scrub_heuristic_pack),
            scrubber_version=SCRUBBER_VERSION,
        )


class GmailActionNeededPhase3ProfileDetector(SharedProfileDetectorEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        config = get_flow_family_config("action_needed", runtime_dir=runtime_dir)
        profile_pack = load_profile_definition_pack(config.profile_detector_pack, runtime_dir=runtime_dir)
        super().__init__(
            taxonomy=profile_pack.taxonomy,
            taxonomy_version=profile_pack.taxonomy_version,
            known_vendor_identities=profile_pack.known_vendor_identities,
            rules=profile_pack.load_rules(),
        )


class GmailActionNeededTemplateRegistry(SharedTemplateRegistry):
    def __init__(self, base_dir: Path | None = None) -> None:
        template_dir = base_dir or get_flow_family_config("action_needed").template_dir
        super().__init__(
            base_dir=template_dir,
            fallback_dirs=[],
            schema_version=TEMPLATE_SCHEMA_VERSION,
            supported_extraction_methods=SUPPORTED_EXTRACTION_METHODS,
            supported_transforms=SUPPORTED_TRANSFORMS,
        )


class GmailActionNeededPhase4Extractor(SharedTemplateExecutionEngine):
    def __init__(self, runtime_dir: Path | None = None) -> None:
        flow_config = get_flow_family_config("action_needed", runtime_dir=runtime_dir)
        super().__init__(
            registry=GmailActionNeededTemplateRegistry(flow_config.template_dir),
            extractor_version=EXTRACTOR_VERSION,
            template_schema_version=TEMPLATE_SCHEMA_VERSION,
            validation_policy=load_validation_policy(flow_config.validation_policy),
        )


class ActionNeededFlowRuntime:
    flow_family = "action_needed"

    def __init__(self, *, runtime_dir: Path | None = None) -> None:
        self.flow_config = get_flow_family_config("action_needed", runtime_dir=runtime_dir)
        self.phase2_scrubber = GmailActionNeededPhase2Scrubber()
        self.phase3_detector = GmailActionNeededPhase3ProfileDetector(runtime_dir=runtime_dir)
        self.phase4_extractor = GmailActionNeededPhase4Extractor(runtime_dir=runtime_dir)
        self.decision_engine = None
        self.output_handler = SharedOutputPersistenceHandler(flow_family="action_needed", runtime_dir=runtime_dir)
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
        return phase4

    def run_probation_shadow_mode(self, phase4):
        return phase4

    def _decide(self, phase4):
        return self.decision_engine.decide(phase4)

    @staticmethod
    def write_action_record(decision, phase4, action_routing) -> ActionNeededActionResult:
        if "store_action_record" not in action_routing.action_intents:
            return ActionNeededActionResult(
                queued=False,
                blocked_reason="no_action_record_intent",
                diagnostics=list(action_routing.diagnostics) + ["action_needed_record:skipped:no_action_record_intent"],
            )
        return ActionNeededActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["action_needed_record:queued"],
        )

    @staticmethod
    def build_user_notification(decision, action_routing, phase4) -> ActionNeededActionResult:
        if "user_notification" not in action_routing.action_intents:
            return ActionNeededActionResult(
                queued=False,
                blocked_reason="no_user_notification_intent",
                diagnostics=list(action_routing.diagnostics) + ["action_needed_notification:skipped:no_user_notification_intent"],
            )
        return ActionNeededActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + ["action_needed_notification:queued"],
        )

    @staticmethod
    def build_followup_action(decision, action_routing, phase4) -> ActionNeededActionResult:
        followup_intents = {"queue_reminder", "mark_high_priority", "mark_for_manual_review"}
        selected = [intent for intent in action_routing.action_intents if intent in followup_intents]
        if not selected:
            return ActionNeededActionResult(
                queued=False,
                blocked_reason="no_followup_intent",
                diagnostics=list(action_routing.diagnostics) + ["action_needed_followup:skipped:no_followup_intent"],
            )
        return ActionNeededActionResult(
            queued=True,
            diagnostics=list(action_routing.diagnostics) + [f"action_needed_followup:queued:{','.join(selected)}"],
        )
