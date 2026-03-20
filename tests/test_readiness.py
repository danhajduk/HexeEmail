from __future__ import annotations

from core.readiness import OperationalReadinessEvaluator


def test_operational_readiness_requires_trust_capabilities_governance_and_connected_provider():
    evaluator = OperationalReadinessEvaluator()

    assert (
        evaluator.evaluate(
            trust_state="trusted",
            capability_declaration_status="accepted",
            governance_sync_status="ok",
            gmail_provider_state="connected",
        )
        is True
    )
    assert (
        evaluator.evaluate(
            trust_state="trusted",
            capability_declaration_status="accepted",
            governance_sync_status="ok",
            gmail_provider_state="configured",
        )
        is False
    )
