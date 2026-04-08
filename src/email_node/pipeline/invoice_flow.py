from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from email_node.flow_families.invoice.runtime import InvoiceFlowRuntime
from email_node.patterns import PatternGenerationRequest, ProbationStore
from email_node.shared_pipeline_core.probation import SharedProbationEvaluator, SharedProbationPromotionManager


class InvoiceFlowPipeline:
    flow_family = "invoice"

    def __init__(
        self,
        *,
        probation_store: ProbationStore | None = None,
        probation_evaluator: SharedProbationEvaluator | None = None,
        probation_promotion: SharedProbationPromotionManager | None = None,
        generate_probation_template: Callable[[PatternGenerationRequest], Awaitable[dict[str, object]]] | None = None,
        ai_calls_enabled: Callable[[], bool] | None = None,
        runtime_dir: Path | None = None,
    ) -> None:
        self.runtime = InvoiceFlowRuntime(
            probation_store=probation_store,
            probation_evaluator=probation_evaluator,
            probation_promotion=probation_promotion,
            generate_probation_template=generate_probation_template,
            ai_calls_enabled=ai_calls_enabled,
            runtime_dir=runtime_dir,
        )
        self.flow_config = self.runtime.flow_config
        self.phase2_scrubber = self.runtime.phase2_scrubber
        self.phase3_detector = self.runtime.phase3_detector
        self.phase4_extractor = self.runtime.phase4_extractor
        self.decision_engine = self.runtime.decision_engine
        self.output_handler = self.runtime.output_handler
        self.action_gate = self.runtime.action_gate
        self.action_router = self.runtime.action_router
        self.shared_core = self.runtime.shared_core

    async def process_normalized_email(self, normalized) -> dict[str, object]:
        return await self.runtime.process_normalized_email(normalized)

    async def attach_probation_template(self, phase4):
        return await self.runtime.attach_probation_template(phase4)
