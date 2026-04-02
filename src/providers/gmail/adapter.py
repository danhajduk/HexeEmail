from __future__ import annotations

from pathlib import Path

from logging_utils import get_logger
from providers.base import EmailProviderAdapter
from providers.gmail.account_store import GmailAccountStore
from providers.gmail.mailbox_client import GmailMailboxClient, GmailMailboxClientError
from providers.gmail.message_store import GmailMessageStore
from providers.gmail.mailbox_status_store import GmailMailboxStatusStore
from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.health import GmailHealthEvaluator
from providers.gmail.identity import GmailIdentityProbeClient
from providers.gmail.models import GmailMailboxStatus, GmailStoredMessage
from providers.gmail.state_machine import GmailAccountStateMachine
from providers.gmail.token_client import GmailTokenExchangeClient
from providers.gmail.token_store import GmailTokenStore
from providers.models import ProviderAccountRecord, ProviderHealth, ProviderId, ProviderState, ProviderValidationResult


LOGGER = get_logger(__name__)


class GmailProviderAdapter(EmailProviderAdapter):
    provider_id = ProviderId.GMAIL.value

    def __init__(
        self,
        runtime_dir: Path,
        *,
        token_client: GmailTokenExchangeClient | None = None,
        identity_client: GmailIdentityProbeClient | None = None,
        mailbox_client: GmailMailboxClient | None = None,
    ) -> None:
        self.config_store = GmailProviderConfigStore(runtime_dir)
        self.account_store = GmailAccountStore(runtime_dir)
        self.token_store = GmailTokenStore(runtime_dir)
        self.mailbox_status_store = GmailMailboxStatusStore(runtime_dir)
        self.message_store = GmailMessageStore(runtime_dir)
        self.state_machine = GmailAccountStateMachine(self.account_store)
        self.token_client = token_client or GmailTokenExchangeClient()
        self.identity_client = identity_client or GmailIdentityProbeClient(self.account_store)
        self.mailbox_client = mailbox_client or GmailMailboxClient()
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
            updated = self.state_machine.transition(account_id, "oauth_pending")
            LOGGER.info(
                "Gmail account entered oauth_pending",
                extra={"event_data": {"account_id": account_id, "status": updated.status}},
            )
            return updated
        return record

    async def complete_oauth_callback(
        self,
        account_id: str,
        code: str,
        *,
        redirect_uri: str,
        code_verifier: str,
        correlation_id: str | None = None,
    ) -> ProviderAccountRecord:
        oauth_config = self.config_store.load()
        current = self.state_machine.ensure_account(account_id)
        if current.status in {"not_configured", "revoked"}:
            self.state_machine.transition(account_id, "oauth_pending")
        token_record = await self.token_client.exchange_authorization_code(
            oauth_config,
            account_id=account_id,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            correlation_id=correlation_id,
        )
        self.token_store.save_token(account_id, token_record)
        if current.status == "oauth_pending":
            self.state_machine.transition(account_id, "token_exchanged")
        elif self.account_store.load_account(account_id).status == "oauth_pending":
            self.state_machine.transition(account_id, "token_exchanged")
        identity_record = await self.identity_client.probe_identity(token_record, correlation_id=correlation_id)
        connected = self.state_machine.transition(account_id, "connected")
        LOGGER.info(
            "Gmail account connected",
            extra={"event_data": {"account_id": account_id, "status": connected.status}},
        )
        return self.account_store.load_account(identity_record.account_id) or identity_record

    async def refresh_mailbox_status(
        self,
        account_id: str,
        *,
        correlation_id: str | None = None,
    ) -> GmailMailboxStatus:
        try:
            oauth_config = self.config_store.load()
        except GmailProviderConfigError as exc:
            snapshot = GmailMailboxStatus(account_id=account_id, status="error", detail=str(exc))
            return self.mailbox_status_store.save_status(snapshot)

        account_record = self.account_store.load_account(account_id)
        token_record = await self.token_client.refresh_if_needed(
            oauth_config,
            account_id=account_id,
            token_store=self.token_store,
            account_store=self.account_store,
            correlation_id=correlation_id,
        )
        if token_record is None:
            snapshot = GmailMailboxStatus(
                account_id=account_id,
                email_address=account_record.email_address if account_record is not None else None,
                status="pending",
                detail="gmail token is not available yet",
            )
            return self.mailbox_status_store.save_status(snapshot)

        try:
            snapshot = await self.mailbox_client.fetch_unread_status(
                token_record=token_record,
                email_address=account_record.email_address if account_record is not None else None,
            )
        except GmailMailboxClientError as exc:
            snapshot = GmailMailboxStatus(
                account_id=account_id,
                email_address=account_record.email_address if account_record is not None else None,
                status="error",
                detail=str(exc),
            )
        return self.mailbox_status_store.save_status(snapshot)

    async def get_mailbox_status(self, account_id: str) -> GmailMailboxStatus | None:
        return self.mailbox_status_store.load_status(account_id)

    async def fetch_messages_for_window(
        self,
        account_id: str,
        *,
        window: str,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        try:
            oauth_config = self.config_store.load()
        except GmailProviderConfigError as exc:
            raise GmailMailboxClientError(str(exc)) from exc

        token_record = await self.token_client.refresh_if_needed(
            oauth_config,
            account_id=account_id,
            token_store=self.token_store,
            account_store=self.account_store,
            correlation_id=correlation_id,
        )
        if token_record is None:
            raise GmailMailboxClientError("gmail token is not available yet")

        query = self.mailbox_client.build_fetch_query(window)
        messages = await self.mailbox_client.fetch_messages(token_record=token_record, query=query)
        stored_count = self.message_store.upsert_messages(messages)
        summary = self.message_store.account_summary(account_id)
        return {
            "provider_id": self.provider_id,
            "account_id": account_id,
            "window": window,
            "query": query,
            "fetched_count": len(messages),
            "stored_count": stored_count,
            "summary": summary,
        }

    async def list_stored_messages(self, account_id: str, *, limit: int = 100) -> list[GmailStoredMessage]:
        return self.message_store.list_messages(account_id, limit=limit)

    async def message_store_summary(self, account_id: str) -> dict[str, object]:
        return self.message_store.account_summary(account_id)

    async def aclose(self) -> None:
        await self.token_client.aclose()
        await self.identity_client.aclose()
        await self.mailbox_client.aclose()
