from __future__ import annotations

from pathlib import Path

from email_node.flow_families.financial.runtime import FinancialFlowRuntime


class FinancialFlowPipeline:
    flow_family = "financial"

    def __init__(self, *, runtime_dir: Path | None = None) -> None:
        self.runtime = FinancialFlowRuntime(runtime_dir=runtime_dir)
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
