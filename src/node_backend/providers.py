from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from providers.gmail.models import GmailTrainingLabel
from providers.registry import ProviderRegistry


class ProviderManager:
    def __init__(self, service: Any) -> None:
        self.service = service

    def build_provider_registry(self) -> ProviderRegistry:
        return ProviderRegistry(self.service.config, gmail_token_client=self.service.gmail_token_client)

    async def provider_status_snapshot_async(self) -> dict[str, object]:
        supported = self.service.provider_registry.list_supported_providers()
        configured: list[str] = []
        enabled: list[str] = []
        summaries: dict[str, object] = {}

        for provider_id in supported:
            adapter = self.service.provider_registry.get_provider(provider_id)
            validation = await adapter.validate_static_config()
            if validation.ok:
                configured.append(provider_id)
            if adapter.get_enabled_status():
                enabled.append(provider_id)
            accounts = await adapter.list_accounts()
            health = None
            if accounts:
                health = (await self.service.email_provider_gateway.gmail_get_account_health(accounts[0].account_id)).model_dump(
                    mode="json"
                )
            summaries[provider_id] = {
                "provider_id": provider_id,
                "provider_state": await adapter.get_provider_state(),
                "enabled": adapter.get_enabled_status(),
                "configured": validation.ok,
                "account_count": len(accounts),
                "accounts": [account.model_dump(mode="json") for account in accounts],
                "health": health,
            }

        return {
            "supported_providers": supported,
            "configured_providers": configured,
            "enabled_providers": enabled,
            "providers": summaries,
        }

    async def gmail_accounts_status(self) -> list[dict[str, object]]:
        adapter = self.service.provider_registry.get_provider("gmail")
        accounts = await adapter.list_accounts()
        return [account.model_dump(mode="json") for account in accounts]

    async def gmail_account_status(self, account_id: str) -> dict[str, object]:
        adapter = self.service.provider_registry.get_provider("gmail")
        account = next((account for account in await adapter.list_accounts() if account.account_id == account_id), None)
        health = await self.service.email_provider_gateway.gmail_get_account_health(account_id)
        mailbox_status = (
            await self.service.email_provider_gateway.gmail_refresh_mailbox_status(account_id, store_unread_messages=False)
            if hasattr(adapter, "refresh_mailbox_status")
            else await adapter.get_mailbox_status(account_id) if hasattr(adapter, "get_mailbox_status") else None
        )
        return {
            "account": account.model_dump(mode="json") if account is not None else None,
            "health": health.model_dump(mode="json"),
            "mailbox_status": mailbox_status.model_dump(mode="json") if mailbox_status is not None else None,
        }

    async def gmail_status(self) -> dict[str, object]:
        adapter = self.service.provider_registry.get_provider("gmail")
        accounts = await adapter.list_accounts()
        fetch_schedule = await adapter.fetch_schedule_state() if hasattr(adapter, "fetch_schedule_state") else None
        statuses: list[dict[str, object]] = []
        for account in accounts:
            mailbox_status = (
                await self.service.email_provider_gateway.gmail_refresh_mailbox_status(
                    account.account_id,
                    store_unread_messages=False,
                )
                if hasattr(adapter, "refresh_mailbox_status")
                else await adapter.get_mailbox_status(account.account_id) if hasattr(adapter, "get_mailbox_status") else None
            )
            labels = (
                await self.service.email_provider_gateway.gmail_available_labels(account.account_id)
                if hasattr(adapter, "available_labels")
                else None
            )
            message_summary = await adapter.message_store_summary(account.account_id) if hasattr(adapter, "message_store_summary") else None
            classification_summary = (
                await adapter.local_classification_summary(account.account_id)
                if hasattr(adapter, "local_classification_summary")
                else None
            )
            sender_reputation = (
                await adapter.sender_reputation_summary(account.account_id)
                if hasattr(adapter, "sender_reputation_summary")
                else None
            )
            model_status = await adapter.training_model_status() if hasattr(adapter, "training_model_status") else None
            spamhaus_summary = await adapter.spamhaus_summary(account.account_id) if hasattr(adapter, "spamhaus_summary") else None
            quota_usage = await adapter.quota_usage_summary(account.account_id) if hasattr(adapter, "quota_usage_summary") else None
            statuses.append(
                {
                    "account": account.model_dump(mode="json"),
                    "mailbox_status": mailbox_status.model_dump(mode="json") if mailbox_status is not None else None,
                    "labels": labels,
                    "message_store": message_summary,
                    "classification_summary": classification_summary,
                    "sender_reputation": sender_reputation,
                    "model_status": model_status,
                    "spamhaus": spamhaus_summary.model_dump(mode="json") if spamhaus_summary is not None else None,
                    "quota_usage": quota_usage.model_dump(mode="json") if quota_usage is not None else None,
                }
            )
        return {
            "provider_id": "gmail",
            "provider_state": await adapter.get_provider_state(),
            "enabled": adapter.get_enabled_status(),
            "fetch_schedule": fetch_schedule.model_dump(mode="json") if fetch_schedule is not None else None,
            "fetch_scheduler": self.service.background_tasks.gmail_fetch_scheduler_state(),
            "last_hour_pipeline": self.service.background_tasks.gmail_last_hour_pipeline_state(),
            "accounts": statuses,
        }

    async def gmail_fetch_messages(
        self,
        window: str,
        *,
        account_id: str = "primary",
        reason: str = "manual",
        slot_key: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        adapter = self.service.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "fetch_messages_for_window"):
            raise ValueError("gmail fetch actions are not available")
        try:
            result = await self.service.email_provider_gateway.gmail_fetch_messages_for_window(
                account_id,
                window=window,
                reason=reason,
                slot_key=slot_key,
                correlation_id=correlation_id,
            )
            if hasattr(adapter, "refresh_mailbox_status"):
                await self.service.email_provider_gateway.gmail_refresh_mailbox_status(
                    account_id,
                    store_unread_messages=False,
                    correlation_id=correlation_id,
                )
            if window == "last_hour":
                result["pipeline"] = await self.run_last_hour_pipeline(
                    account_id=account_id,
                    mode=reason,
                    fetched_count=int(result.get("fetched_count") or 0),
                    correlation_id=correlation_id,
                )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return result

    async def run_last_hour_pipeline(
        self,
        *,
        account_id: str,
        mode: str,
        fetched_count: int,
        correlation_id: str | None,
    ) -> dict[str, object]:
        started_at = datetime.now(UTC).isoformat()
        state = self.service.background_tasks.save_gmail_last_hour_pipeline_state(
            mode=mode,
            status="running",
            detail="Running last-hour Gmail pipeline...",
            started_at=started_at,
            updated_at=started_at,
            stages={
                "fetch": {
                    "status": "completed",
                    "detail": f"Fetched {fetched_count} last-hour emails.",
                    "count": fetched_count,
                },
                "spamhaus": {"status": "running", "detail": "Checking pending Spamhaus items...", "count": 0},
                "local_classification": {"status": "idle", "detail": "Waiting", "count": 0},
                "ai_classification": {"status": "idle", "detail": "Waiting", "count": 0},
            },
        )
        adapter = self.service.provider_registry.get_provider("gmail")
        try:
            spamhaus_summary = await adapter.spamhaus_summary(account_id)
            spamhaus_count = 0
            spamhaus_detail = "No pending Spamhaus items."
            spamhaus_status = "idle"
            if spamhaus_summary.pending_count > 0:
                spamhaus_result = await adapter.check_spamhaus_for_stored_messages(account_id)
                spamhaus_count = int(spamhaus_result.get("checked_count") or 0)
                spamhaus_detail = f"Checked {spamhaus_count} pending Spamhaus items."
                spamhaus_status = "completed"
            state["stages"]["spamhaus"] = {
                "status": spamhaus_status,
                "detail": spamhaus_detail,
                "count": spamhaus_count,
            }
            self.service.background_tasks.save_gmail_last_hour_pipeline_state(
                stages=state["stages"],
                updated_at=datetime.now(UTC).isoformat(),
            )

            last_hour_start = datetime.now().astimezone() - timedelta(hours=1)
            recent_messages = adapter.message_store.list_messages_received_since(account_id, since=last_hour_start)
            checked_ids = adapter.message_store.list_spamhaus_checked_message_ids(account_id)
            local_candidates = [
                message
                for message in recent_messages
                if message.message_id in checked_ids
                and (message.local_label is None or message.local_label == GmailTrainingLabel.UNKNOWN.value)
            ]
            local_stage_status = "idle"
            local_detail = "No last-hour unknown emails needed local classification."
            local_count, ai_candidates = self.service._classify_candidates_locally(
                account_id=account_id,
                candidates=local_candidates,
            )
            if local_count > 0 and hasattr(adapter, "refresh_sender_reputations"):
                await adapter.refresh_sender_reputations(account_id)
            if local_candidates and local_count > 0:
                local_stage_status = "completed"
                local_detail = f"Locally classified {local_count} last-hour emails."
            elif local_candidates:
                local_stage_status = "idle"
                local_detail = "Skipped local classification because no trained local model is available."
            state["stages"]["local_classification"] = {
                "status": local_stage_status,
                "detail": local_detail,
                "count": local_count,
            }
            self.service.background_tasks.save_gmail_last_hour_pipeline_state(
                stages=state["stages"],
                updated_at=datetime.now(UTC).isoformat(),
            )

            if not self.service.runtime.runtime_ai_calls_enabled():
                skipped_count = len(ai_candidates)
                state["stages"]["ai_classification"] = {
                    "status": "idle",
                    "detail": (
                        f"Skipped {skipped_count} last-hour AI candidates because AI calls are disabled."
                        if skipped_count > 0
                        else "AI calls are disabled and no last-hour unknown emails needed AI classification."
                    ),
                    "count": 0,
                }
            else:
                ai_results, _ = await self.service._execute_email_classifier_for_messages(
                    account_id=account_id,
                    messages=ai_candidates,
                    target_api_base_url="http://127.0.0.1:9002",
                    correlation_id=correlation_id,
                )
                ai_count = len(ai_results)
                state["stages"]["ai_classification"] = {
                    "status": "completed" if ai_count > 0 else "idle",
                    "detail": (
                        f"Sent {ai_count} last-hour unknown emails to the AI node."
                        if ai_count > 0
                        else "No last-hour unknown emails needed AI classification."
                    ),
                    "count": ai_count,
                }
            completed_at = datetime.now(UTC).isoformat()
            return self.service.background_tasks.save_gmail_last_hour_pipeline_state(
                status="completed",
                detail="Last-hour Gmail pipeline completed.",
                stages=state["stages"],
                updated_at=completed_at,
                last_completed_at=completed_at,
            )
        except Exception as exc:
            failed_at = datetime.now(UTC).isoformat()
            return self.service.background_tasks.save_gmail_last_hour_pipeline_state(
                mode=mode,
                status="failed",
                detail=str(exc),
                stages=state["stages"],
                updated_at=failed_at,
            )
