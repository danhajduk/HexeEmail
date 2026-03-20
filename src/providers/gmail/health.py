from __future__ import annotations

from providers.gmail.config_store import GmailProviderConfigStore
from providers.gmail.models import GmailOAuthConfig, GmailTokenRecord
from providers.models import ProviderAccountRecord, ProviderHealth, ProviderId


class GmailHealthEvaluator:
    def evaluate(
        self,
        oauth_config: GmailOAuthConfig,
        *,
        account_id: str,
        token_record: GmailTokenRecord | None,
        account_record: ProviderAccountRecord | None,
    ) -> ProviderHealth:
        validation = GmailProviderConfigStore.validate_static(oauth_config)
        if not oauth_config.enabled or not validation.ok:
            return ProviderHealth(
                provider_id=ProviderId.GMAIL,
                account_id=account_id,
                status="invalid_config",
                detail="Gmail provider configuration is invalid or disabled.",
            )

        if account_record is not None and account_record.status == "revoked":
            return ProviderHealth(
                provider_id=ProviderId.GMAIL,
                account_id=account_id,
                status="revoked",
                detail="Gmail account access has been revoked.",
            )

        if token_record is None:
            return ProviderHealth(
                provider_id=ProviderId.GMAIL,
                account_id=account_id,
                status="oauth_pending",
                detail="Gmail oauth is required before the account can be used.",
            )

        required_scopes = set(oauth_config.requested_scopes.scopes)
        granted_scopes = set(token_record.granted_scopes)
        if required_scopes and not required_scopes.issubset(granted_scopes):
            return ProviderHealth(
                provider_id=ProviderId.GMAIL,
                account_id=account_id,
                status="degraded",
                detail="Granted Gmail scopes do not satisfy the configured requirement set.",
            )

        if token_record.refresh_token is None:
            return ProviderHealth(
                provider_id=ProviderId.GMAIL,
                account_id=account_id,
                status="degraded",
                detail="Refresh token is missing, so long-lived Gmail access is not ready.",
            )

        if account_record is None or not account_record.email_address:
            return ProviderHealth(
                provider_id=ProviderId.GMAIL,
                account_id=account_id,
                status="degraded",
                detail="Gmail account identity has not been confirmed yet.",
            )

        return ProviderHealth(
            provider_id=ProviderId.GMAIL,
            account_id=account_id,
            status="connected",
            detail=f"Gmail account {account_record.email_address} is connected.",
        )
