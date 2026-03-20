from __future__ import annotations


class OperationalReadinessEvaluator:
    def evaluate(
        self,
        *,
        trust_state: str,
        capability_declaration_status: str | None,
        governance_sync_status: str | None,
        gmail_provider_state: str,
    ) -> bool:
        return (
            trust_state == "trusted"
            and capability_declaration_status == "accepted"
            and governance_sync_status == "ok"
            and gmail_provider_state == "connected"
        )
