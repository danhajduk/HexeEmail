from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from email_node.actions.tracking_monitor_handler import TrackingMonitorHandler
from email_node.actions.user_notification_handler import UserNotificationHandler
from email_node.flow_families.order.runtime import OrderFlowRuntime
from email_node.orders.order_record_service import OrderRecordService
from email_node.patterns import PatternGenerationRequest
from email_node.patterns.probation_evaluator import ProbationEvaluator
from email_node.patterns.probation_promotion import ProbationPromotionManager
from email_node.patterns.probation_store import ProbationStore
from email_node.pipeline.order_action_gate import OrderActionGate
from email_node.pipeline.order_action_router import OrderActionRouter
from email_node.pipeline.order_decision_engine import OrderDecisionEngine
from email_node.pipeline.order_output_handler import OrderOutputHandler
from providers.gmail.order_phase2 import GmailOrderPhase2Scrubber
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


class OrderFlowPipeline:
    flow_family = "order"

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
        self.runtime = OrderFlowRuntime(
            phase2_scrubber=phase2_scrubber,
            phase3_detector=phase3_detector,
            phase4_extractor=phase4_extractor,
            probation_store=probation_store,
            probation_evaluator=probation_evaluator,
            probation_promotion=probation_promotion,
            generate_probation_template=generate_probation_template,
            ai_calls_enabled=ai_calls_enabled,
            order_checks_enabled=order_checks_enabled,
            decision_engine=decision_engine,
            output_handler=output_handler,
            action_gate=action_gate,
            action_router=action_router,
            order_record_service=order_record_service,
            user_notification_handler=user_notification_handler,
            tracking_monitor_handler=tracking_monitor_handler,
            runtime_dir=runtime_dir,
        )
        self.flow_config = self.runtime.flow_config
        self.phase2_scrubber = self.runtime.phase2_scrubber
        self.phase3_detector = self.runtime.phase3_detector
        self.phase4_extractor = self.runtime.phase4_extractor
        self.probation_store = self.runtime.probation_store
        self.probation_evaluator = self.runtime.probation_evaluator
        self.probation_promotion = self.runtime.probation_promotion
        self.decision_engine = self.runtime.decision_engine
        self.output_handler = self.runtime.output_handler
        self.action_gate = self.runtime.action_gate
        self.action_router = self.runtime.action_router
        self.order_record_service = self.runtime.order_record_service
        self.user_notification_handler = self.runtime.user_notification_handler
        self.tracking_monitor_handler = self.runtime.tracking_monitor_handler
        self.shared_core = self.runtime.shared_core

    async def process_normalized_email(self, normalized) -> dict[str, object]:
        return await self.runtime.process_normalized_email(normalized)

    async def attach_probation_template(self, phase4):
        return await self.runtime.attach_probation_template(phase4)

    def _run_probation_shadow_mode(self, phase4):
        return self.runtime.run_probation_shadow_mode(phase4)
