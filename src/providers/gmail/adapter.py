from __future__ import annotations

from providers.base import EmailProviderAdapter
from providers.models import ProviderAccountRecord, ProviderHealth, ProviderId, ProviderState, ProviderValidationResult


class GmailProviderAdapter(EmailProviderAdapter):
    provider_id = ProviderId.GMAIL.value

    async def validate_static_config(self) -> ProviderValidationResult:
        return ProviderValidationResult(
            ok=False,
            missing_fields=["client_id", "client_secret", "redirect_uri"],
            messages=["Gmail provider configuration has not been added yet."],
        )

    async def get_provider_state(self) -> ProviderState:
        return "not_configured"

    async def list_accounts(self) -> list[ProviderAccountRecord]:
        return []

    async def get_account_health(self, account_id: str) -> ProviderHealth:
        return ProviderHealth(
            provider_id=ProviderId.GMAIL,
            status="invalid_config",
            detail=f"Gmail adapter skeleton is registered but account {account_id} is not connected.",
        )

    def get_enabled_status(self) -> bool:
        return False
