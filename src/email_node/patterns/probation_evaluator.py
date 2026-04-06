from __future__ import annotations

from email_node.shared_pipeline_core.probation import SharedProbationEvaluator
from email_node.patterns.probation_evaluation_result import ProbationEvaluationResult
from email_node.patterns.probation_store import ProbationStore
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


class ProbationEvaluator(SharedProbationEvaluator):
    def __init__(
        self,
        *,
        probation_store: ProbationStore,
        extractor: GmailOrderPhase4Extractor | None = None,
    ) -> None:
        super().__init__(probation_store=probation_store, extractor=extractor or GmailOrderPhase4Extractor())
