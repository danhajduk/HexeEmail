from __future__ import annotations

from datetime import datetime
from pathlib import Path

from logging_utils import get_logger
from providers.base import EmailProviderAdapter
from providers.gmail.account_store import GmailAccountStore
from providers.gmail.fetch_schedule_store import GmailFetchScheduleStore
from providers.gmail.label_cache_store import GmailLabelCacheStore
from providers.gmail.mailbox_client import GmailMailboxClient, GmailMailboxClientError
from providers.gmail.message_store import GmailMessageStore
from providers.gmail.mailbox_status_store import GmailMailboxStatusStore
from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.health import GmailHealthEvaluator
from providers.gmail.identity import GmailIdentityProbeClient
from providers.gmail.models import (
    GmailFetchScheduleState,
    GmailMailboxStatus,
    GmailManualClassificationBatchInput,
    GmailQuotaUsageSnapshot,
    GmailSemiAutoClassificationBatchInput,
    GmailSpamhausSummary,
    GmailStoredMessage,
    GmailTrainingLabel,
)
from providers.gmail.quota_tracker import GmailQuotaTracker
from providers.gmail.spamhaus_checker import GmailSpamhausChecker
from providers.gmail.state_machine import GmailAccountStateMachine
from providers.gmail.token_client import GmailTokenExchangeClient
from providers.gmail.token_store import GmailTokenStore
from providers.gmail.training import flatten_message, render_flat_training_text, render_raw_training_text
from providers.gmail.training import build_training_dataset
from providers.gmail.training_model import GmailTrainingModelStore
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
        self.fetch_schedule_store = GmailFetchScheduleStore(runtime_dir)
        self.label_cache_store = GmailLabelCacheStore(runtime_dir)
        self.quota_tracker = GmailQuotaTracker(runtime_dir)
        self.state_machine = GmailAccountStateMachine(self.account_store)
        self.token_client = token_client or GmailTokenExchangeClient()
        self.identity_client = identity_client or GmailIdentityProbeClient(self.account_store)
        self.mailbox_client = mailbox_client or GmailMailboxClient(quota_tracker=self.quota_tracker)
        if getattr(self.mailbox_client, "quota_tracker", None) is None:
            self.mailbox_client.quota_tracker = self.quota_tracker
        self.spamhaus_checker = GmailSpamhausChecker()
        self.training_model_store = GmailTrainingModelStore(runtime_dir)
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
        store_unread_messages: bool = True,
        correlation_id: str | None = None,
    ) -> GmailMailboxStatus:
        account_record = self.account_store.load_account(account_id)
        snapshot = self.message_store.mailbox_status(
            account_id,
            email_address=account_record.email_address if account_record is not None else None,
        )
        return self.mailbox_status_store.save_status(snapshot)

    async def get_mailbox_status(self, account_id: str) -> GmailMailboxStatus | None:
        return self.mailbox_status_store.load_status(account_id)

    async def fetch_messages_for_window(
        self,
        account_id: str,
        *,
        window: str,
        reason: str = "manual",
        slot_key: str | None = None,
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
        if getattr(self.mailbox_client, "quota_tracker", None) is None:
            self.mailbox_client.quota_tracker = self.quota_tracker

        query = self.mailbox_client.build_fetch_query(window)
        fetched_count = 0
        stored_count = 0
        async for batch_messages in self.mailbox_client.iter_message_batches(token_record=token_record, query=query):
            fetched_count += len(batch_messages)
            stored_count += self.message_store.upsert_messages(batch_messages)
        summary = self.message_store.account_summary(account_id)
        window_reason = "scheduled" if reason == "scheduled" else "manual"
        if window in {"yesterday", "today", "last_hour"}:
            schedule_state = self.fetch_schedule_store.load_state()
            window_state = getattr(schedule_state, window)
            window_state.last_run_at = datetime.now().astimezone()
            window_state.last_run_reason = window_reason
            window_state.last_slot_key = slot_key
            self.fetch_schedule_store.save_state(schedule_state)
        return {
            "provider_id": self.provider_id,
            "account_id": account_id,
            "window": window,
            "query": query,
            "fetched_count": fetched_count,
            "stored_count": stored_count,
            "summary": summary,
            "reason": window_reason,
            "slot_key": slot_key,
        }

    async def list_stored_messages(self, account_id: str, *, limit: int = 100) -> list[GmailStoredMessage]:
        return self.message_store.list_messages(account_id, limit=limit)

    async def message_store_summary(self, account_id: str) -> dict[str, object]:
        return self.message_store.account_summary(account_id)

    async def available_labels(self, account_id: str, *, refresh: bool = True) -> dict[str, object]:
        account_record = self.account_store.load_account(account_id)
        cached = self.label_cache_store.load(account_id)
        if not refresh:
            return cached
        token_record = self.token_store.load_token(account_id)
        if token_record is None:
            return cached
        try:
            labels = await self.mailbox_client.fetch_labels(token_record=token_record)
        except GmailMailboxClientError:
            return cached
        return self.label_cache_store.save(account_id, labels)

    async def local_classification_summary(self, account_id: str) -> dict[str, object]:
        return self.message_store.local_classification_summary(account_id)

    async def training_model_status(self) -> dict[str, object]:
        return self.training_model_store.status()

    async def training_dataset_summary(self, account_id: str, *, bootstrap_threshold: float) -> dict[str, object]:
        account_record = self.account_store.load_account(account_id)
        dataset, summary = build_training_dataset(
            self.message_store.list_all_messages(account_id),
            my_addresses=[account_record.email_address] if account_record and account_record.email_address else [],
            bootstrap_threshold=bootstrap_threshold,
        )
        del dataset
        return summary.model_dump(mode="json")

    async def spamhaus_summary(self, account_id: str) -> GmailSpamhausSummary:
        return self.message_store.spamhaus_summary(account_id)

    async def quota_usage_summary(self, account_id: str) -> GmailQuotaUsageSnapshot:
        return self.quota_tracker.snapshot(account_id)

    async def manual_training_batch(self, account_id: str, *, threshold: float, limit: int = 40) -> dict[str, object]:
        account_record = self.account_store.load_account(account_id)
        messages = self.message_store.list_training_candidates(account_id, limit=limit, threshold=threshold)
        label_names = self.label_cache_store.id_name_map(account_id)
        flattened = [flatten_message(message, account_email=account_record.email_address if account_record is not None else None) for message in messages]
        return {
            "provider_id": self.provider_id,
            "account_id": account_id,
            "threshold": threshold,
            "count": len(flattened),
            "source": "manual",
            "items": [
                {
                    **item.model_dump(mode="json"),
                    "flat_text": render_flat_training_text(item),
                    "raw_text": render_raw_training_text(message, label_names=label_names),
                }
                for message, item in zip(messages, flattened, strict=False)
            ],
        }

    async def save_manual_classifications(self, account_id: str, batch: GmailManualClassificationBatchInput) -> dict[str, object]:
        saved = 0
        for item in batch.items:
            self.message_store.update_local_classification(
                account_id,
                item.message_id,
                label=item.label,
                confidence=1.0,
                manual_classification=True,
            )
            saved += 1
        return {"provider_id": self.provider_id, "account_id": account_id, "saved_count": saved}

    async def train_local_model(self, account_id: str, *, bootstrap_threshold: float) -> dict[str, object]:
        account_record = self.account_store.load_account(account_id)
        dataset, summary = build_training_dataset(
            self.message_store.list_all_messages(account_id),
            my_addresses=[account_record.email_address] if account_record and account_record.email_address else [],
            bootstrap_threshold=bootstrap_threshold,
        )
        status = self.training_model_store.train_classifier(dataset, dataset_summary=summary)
        return {
            "provider_id": self.provider_id,
            "account_id": account_id,
            "model_status": status,
            "dataset_summary": summary.model_dump(mode="json"),
        }

    async def semi_auto_training_batch(self, account_id: str, *, threshold: float, limit: int = 20) -> dict[str, object]:
        account_record = self.account_store.load_account(account_id)
        messages = self.message_store.list_oldest_training_candidates(account_id, limit=limit, threshold=threshold)
        label_names = self.label_cache_store.id_name_map(account_id)
        flattened = [flatten_message(message, account_email=account_record.email_address if account_record is not None else None) for message in messages]
        predictions = self.training_model_store.predict(
            [render_flat_training_text(item) for item in flattened],
            threshold=threshold,
        )
        items: list[dict[str, object]] = []
        for message, item, prediction in zip(messages, flattened, predictions, strict=False):
            predicted_label = prediction["predicted_label"]
            predicted_confidence = prediction["predicted_confidence"]
            items.append(
                {
                    **item.model_dump(mode="json"),
                    "flat_text": render_flat_training_text(item),
                    "raw_text": render_raw_training_text(message, label_names=label_names),
                    "predicted_label": predicted_label,
                    "predicted_confidence": predicted_confidence,
                    "raw_predicted_label": prediction["raw_predicted_label"],
                }
            )
        return {
            "provider_id": self.provider_id,
            "account_id": account_id,
            "threshold": threshold,
            "count": len(items),
            "source": "semi_auto",
            "items": items,
        }

    async def save_semi_auto_review(self, account_id: str, batch: GmailSemiAutoClassificationBatchInput) -> dict[str, object]:
        saved = 0
        manual_count = 0
        for item in batch.items:
            changed = item.selected_label != item.predicted_label
            self.message_store.update_local_classification(
                account_id,
                item.message_id,
                label=item.selected_label,
                confidence=1.0 if changed else item.predicted_confidence,
                manual_classification=changed,
            )
            if changed:
                manual_count += 1
            saved += 1
        return {
            "provider_id": self.provider_id,
            "account_id": account_id,
            "saved_count": saved,
            "manual_count": manual_count,
        }

    async def check_spamhaus_for_stored_messages(self, account_id: str) -> dict[str, object]:
        pending_messages = self.message_store.list_messages_pending_spamhaus(account_id)
        checked_count = 0
        listed_count = 0
        error_count = 0

        for message in pending_messages:
            check = await self.spamhaus_checker.check_sender(
                account_id=account_id,
                message_id=message.message_id,
                sender=message.sender,
            )
            saved_check = self.message_store.upsert_spamhaus_check(check)
            checked_count += 1
            if saved_check.listed:
                listed_count += 1
            if saved_check.status == "error":
                error_count += 1

        summary = self.message_store.spamhaus_summary(account_id)
        return {
            "provider_id": self.provider_id,
            "account_id": account_id,
            "checked_count": checked_count,
            "listed_count": listed_count,
            "error_count": error_count,
            "summary": summary.model_dump(mode="json"),
        }

    async def fetch_schedule_state(self) -> GmailFetchScheduleState:
        return self.fetch_schedule_store.load_state()

    async def aclose(self) -> None:
        await self.token_client.aclose()
        await self.identity_client.aclose()
        await self.mailbox_client.aclose()
