from __future__ import annotations

from pathlib import Path

from providers.base import EmailProviderAdapter
from providers.gmail.account_store import GmailAccountStore
from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.health import GmailHealthEvaluator
from providers.gmail.identity import GmailIdentityProbeClient
from providers.gmail.state_machine import GmailAccountStateMachine
from providers.gmail.token_client import GmailTokenExchangeClient
from providers.gmail.token_store import GmailTokenStore
from providers.models import ProviderAccountRecord, ProviderHealth, ProviderId, ProviderState, ProviderValidationResult


class GmailProviderAdapter(EmailProviderAdapter):
    provider_id = ProviderId.GMAIL.value

    def __init__(
        self,
        runtime_dir: Path,
        *,
        token_client: GmailTokenExchangeClient | None = None,
        identity_client: GmailIdentityProbeClient | None = None,
    ) -> None:
        self.config_store = GmailProviderConfigStore(runtime_dir)
        self.account_store = GmailAccountStore(runtime_dir)
        self.token_store = GmailTokenStore(runtime_dir)
        self.state_machine = GmailAccountStateMachine(self.account_store)
        self.token_client = token_client or GmailTokenExchangeClient()
        self.identity_client = identity_client or GmailIdentityProbeClient(self.account_store)
        self.health_evaluator = GmailHealthEvaluator()

    async def validate_static_config(self) -> ProviderValidationResult:
        try:
            config = self.config_store.load()
        except GmailProviderConfigError as exc:
            return ProviderValidationResult(ok=False, messages=[str(exc)])
        return self.config_store.validate(config)

    async def get_provider_state(self) -> ProviderState:
        try:
            config = self.config_store.load()
        except GmailProviderConfigError:
            return "not_configured"
        validation = self.config_store.validate(config)
        if not config.enabled:
            return "disabled"
        if not validation.ok:
            return "not_configured"

        accounts = self.account_store.list_accounts()
        if not accounts:
            return "configured"
        statuses = {account.status for account in accounts}
        if "connected" in statuses:
            return "connected"
        if "degraded" in statuses:
            return "degraded"
        if "oauth_pending" in statuses:
            return "oauth_pending"
        if statuses == {"revoked"}:
            return "revoked"
        return "configured"

    async def list_accounts(self) -> list[ProviderAccountRecord]:
        return self.account_store.list_accounts()

    async def get_account_health(self, account_id: str) -> ProviderHealth:
        try:
            oauth_config = self.config_store.load()
        except GmailProviderConfigError:
            return ProviderHealth(
                provider_id=ProviderId.GMAIL,
                account_id=account_id,
                status="invalid_config",
                detail=f"Gmail provider configuration is not available for account {account_id}.",
            )
        token_record = await self.token_client.refresh_if_needed(
            oauth_config,
            account_id=account_id,
            token_store=self.token_store,
            account_store=self.account_store,
        )
        account_record = self.account_store.load_account(account_id)
        return self.health_evaluator.evaluate(
            oauth_config,
            account_id=account_id,
            token_record=token_record,
            account_record=account_record,
        )

    def get_enabled_status(self) -> bool:
        try:
            return self.config_store.load().enabled
        except GmailProviderConfigError:
            return False

    async def start_account_connect(self, account_id: str) -> ProviderAccountRecord:
        record = self.state_machine.ensure_account(account_id)
        if record.status in {"not_configured", "revoked"}:
            return self.state_machine.transition(account_id, "oauth_pending")
        return record

    async def complete_oauth_callback(self, account_id: str, code: str, *, correlation_id: str | None = None) -> ProviderAccountRecord:
        oauth_config = self.config_store.load()
        current = self.state_machine.ensure_account(account_id)
        if current.status in {"not_configured", "revoked"}:
            self.state_machine.transition(account_id, "oauth_pending")
        token_record = await self.token_client.exchange_authorization_code(
            oauth_config,
            account_id=account_id,
            code=code,
            correlation_id=correlation_id,
        )
        self.token_store.save_token(account_id, token_record)
        if current.status == "oauth_pending":
            self.state_machine.transition(account_id, "token_exchanged")
        elif self.account_store.load_account(account_id).status == "oauth_pending":
            self.state_machine.transition(account_id, "token_exchanged")
        identity_record = await self.identity_client.probe_identity(token_record, correlation_id=correlation_id)
        self.state_machine.transition(account_id, "connected")
        return self.account_store.load_account(identity_record.account_id) or identity_record
