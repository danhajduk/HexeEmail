from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from logging_utils import get_logger
from node_models.runtime import RuntimePromptExecutionRequestInput


LOGGER = get_logger(__name__)
AI_LOGGER = get_logger("hexe.ai.runtime")
GMAIL_POLL_LOGGER = get_logger("hexe.providers.gmail.polling")
TERMINAL_ONBOARDING_STATES = {"approved", "rejected", "expired", "consumed", "invalid"}


@dataclass(frozen=True)
class ScheduleTemplate:
    name: str
    detail: str
    next_run_resolver: Callable[[datetime], datetime | None]


class BackgroundTaskManager:
    def __init__(self, service: Any) -> None:
        self.service = service
        self.finalize_polling_task: asyncio.Task | None = None
        self.gmail_status_task: asyncio.Task | None = None
        self.gmail_fetch_task: asyncio.Task | None = None

    @staticmethod
    def default_gmail_last_hour_pipeline_state() -> dict[str, object]:
        return {
            "mode": "idle",
            "status": "idle",
            "detail": "No last-hour pipeline run yet.",
            "started_at": None,
            "updated_at": None,
            "last_completed_at": None,
            "stages": {
                "fetch": {"status": "idle", "detail": "Waiting", "count": 0},
                "spamhaus": {"status": "idle", "detail": "Waiting", "count": 0},
                "local_classification": {"status": "idle", "detail": "Waiting", "count": 0},
                "ai_classification": {"status": "idle", "detail": "Waiting", "count": 0},
            },
        }

    @staticmethod
    def default_gmail_fetch_scheduler_state() -> dict[str, object]:
        return {
            "loop_enabled": False,
            "loop_active": False,
            "status": "idle",
            "detail": "Gmail fetch scheduler has not started yet.",
            "last_checked_at": None,
            "last_due_windows": [],
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error_at": None,
            "last_error": None,
        }

    def gmail_fetch_scheduler_state(self) -> dict[str, object]:
        state = dict(self.default_gmail_fetch_scheduler_state())
        persisted = (
            self.service.state.gmail_fetch_scheduler_state
            if isinstance(self.service.state.gmail_fetch_scheduler_state, dict)
            else {}
        )
        state.update(persisted)
        state["loop_enabled"] = bool(self.service.config.gmail_fetch_poll_on_startup)
        state["loop_active"] = bool(self.gmail_fetch_task is not None and not self.gmail_fetch_task.done())
        return state

    def save_gmail_fetch_scheduler_state(self, **updates: object) -> dict[str, object]:
        state = self.gmail_fetch_scheduler_state()
        state.update(updates)
        self.service.state.gmail_fetch_scheduler_state = state
        self.service.state_store.save(self.service.state)
        return state

    def gmail_last_hour_pipeline_state(self) -> dict[str, object]:
        state = dict(self.default_gmail_last_hour_pipeline_state())
        persisted = (
            self.service.state.gmail_last_hour_pipeline_state
            if isinstance(self.service.state.gmail_last_hour_pipeline_state, dict)
            else {}
        )
        state.update(persisted)
        default_stages = dict(self.default_gmail_last_hour_pipeline_state()["stages"])
        persisted_stages = persisted.get("stages") if isinstance(persisted.get("stages"), dict) else {}
        default_stages.update(persisted_stages)
        state["stages"] = default_stages
        return state

    def save_gmail_last_hour_pipeline_state(self, **updates: object) -> dict[str, object]:
        state = self.gmail_last_hour_pipeline_state()
        state.update(updates)
        self.service.state.gmail_last_hour_pipeline_state = state
        self.service.state_store.save(self.service.state)
        return state

    @staticmethod
    def next_daily_run(now: datetime, *, hour: int, minute: int) -> datetime:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return candidate

    @staticmethod
    def next_today_window_run(now: datetime) -> datetime:
        for hour in (0, 6, 12, 18):
            candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if candidate > now:
                return candidate
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def next_five_minute_run(now: datetime) -> datetime:
        total_minutes = now.hour * 60 + now.minute
        next_total_minutes = ((total_minutes // 5) + 1) * 5
        day_offset, minute_of_day = divmod(next_total_minutes, 24 * 60)
        hour, minute = divmod(minute_of_day, 60)
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if day_offset:
            candidate = candidate + timedelta(days=day_offset)
        return candidate

    @staticmethod
    def next_hourly_run(now: datetime) -> datetime:
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    @staticmethod
    def next_weekly_run(now: datetime, *, weekday: int = 0, hour: int = 0, minute: int = 1) -> datetime:
        days_ahead = (weekday - now.weekday()) % 7
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        if candidate <= now:
            candidate = candidate + timedelta(days=7)
        return candidate

    @staticmethod
    def next_bi_weekly_run(
        now: datetime,
        *,
        anchor: tuple[int, int, int] = (2026, 1, 5),
        weekday: int = 0,
        hour: int = 0,
        minute: int = 1,
    ) -> datetime:
        anchor_date = now.replace(
            year=anchor[0],
            month=anchor[1],
            day=anchor[2],
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        candidate = anchor_date
        if candidate.weekday() != weekday:
            candidate = candidate + timedelta(days=(weekday - candidate.weekday()) % 7)
        while candidate <= now:
            candidate = candidate + timedelta(days=14)
        return candidate

    @staticmethod
    def next_monthly_run(now: datetime, *, day: int = 1, hour: int = 0, minute: int = 1) -> datetime:
        year = now.year
        month = now.month
        candidate = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            candidate = candidate.replace(year=year, month=month, day=day)
        return candidate

    @staticmethod
    def next_every_other_day_run(
        now: datetime,
        *,
        anchor: tuple[int, int, int] = (2026, 1, 1),
        hour: int = 0,
        minute: int = 1,
    ) -> datetime:
        anchor_date = now.replace(
            year=anchor[0],
            month=anchor[1],
            day=anchor[2],
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        candidate = anchor_date
        while candidate <= now:
            candidate = candidate + timedelta(days=2)
        return candidate

    @staticmethod
    def next_twice_a_week_run(now: datetime, *, weekdays: tuple[int, int] = (0, 3), hour: int = 0, minute: int = 1) -> datetime:
        candidates = [
            now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=(weekday - now.weekday()) % 7)
            for weekday in weekdays
        ]
        future_candidates = [candidate for candidate in candidates if candidate > now]
        if future_candidates:
            return min(future_candidates)
        return min(candidate + timedelta(days=7) for candidate in candidates)

    @classmethod
    def schedule_templates(cls) -> dict[str, ScheduleTemplate]:
        return {
            "daily": ScheduleTemplate("daily", "Every day at 00:01", lambda now: cls.next_daily_run(now, hour=0, minute=1)),
            "weekly": ScheduleTemplate("weekly", "Monday 00:01", lambda now: cls.next_weekly_run(now, weekday=0, hour=0, minute=1)),
            "4_times_a_day": ScheduleTemplate("4_times_a_day", "00:00, 06:00, 12:00, 18:00", cls.next_today_window_run),
            "every_5_minutes": ScheduleTemplate("every_5_minutes", "00:05, 00:10, 00:15, ...", cls.next_five_minute_run),
            "hourly": ScheduleTemplate("hourly", "Hourly at :00", cls.next_hourly_run),
            "bi_weekly": ScheduleTemplate("bi_weekly", "Every 2 weeks", lambda now: cls.next_bi_weekly_run(now, weekday=0, hour=0, minute=1)),
            "monthly": ScheduleTemplate("monthly", "First day of each month at 00:01", lambda now: cls.next_monthly_run(now, day=1, hour=0, minute=1)),
            "every_other_day": ScheduleTemplate("every_other_day", "Every other day at 00:01", lambda now: cls.next_every_other_day_run(now, hour=0, minute=1)),
            "twice_a_week": ScheduleTemplate("twice_a_week", "Monday and Thursday at 00:01", lambda now: cls.next_twice_a_week_run(now, weekdays=(0, 3), hour=0, minute=1)),
            "on_start": ScheduleTemplate("on_start", "Runs once after full operational readiness", lambda now: None),
        }

    @classmethod
    def schedule_template_detail(cls, schedule_name: str) -> str:
        template = cls.schedule_templates().get(schedule_name)
        return template.detail if template is not None else schedule_name

    @classmethod
    def schedule_template_next_run(cls, schedule_name: str, now: datetime) -> datetime | None:
        template = cls.schedule_templates().get(schedule_name)
        if template is None:
            return None
        return template.next_run_resolver(now)

    @classmethod
    def scheduled_task_entry(
        cls,
        *,
        task_id: str,
        title: str,
        group: str,
        schedule_name: str,
        status: str,
        last_execution_at: str | None,
        next_execution_at: str | None,
        last_reason: str | None,
        detail: str,
        last_slot_key: str | None = None,
        schedule_detail: str | None = None,
    ) -> dict[str, object]:
        return {
            "task_id": task_id,
            "title": title,
            "group": group,
            "schedule_name": schedule_name,
            "schedule_detail": schedule_detail or cls.schedule_template_detail(schedule_name),
            "status": status,
            "last_execution_at": last_execution_at,
            "next_execution_at": next_execution_at,
            "last_reason": last_reason,
            "detail": detail,
            "last_slot_key": last_slot_key,
        }

    @classmethod
    def scheduled_task_legend(cls) -> list[dict[str, str]]:
        return [{"name": template.name, "detail": template.detail} for template in cls.schedule_templates().values()]

    def scheduled_tasks_snapshot(self) -> list[dict[str, object]]:
        local_now = datetime.now().astimezone()
        fetch_schedule_state = None
        gmail_adapter = self.service.provider_registry.get_provider("gmail")
        if hasattr(gmail_adapter, "fetch_schedule_state"):
            fetch_schedule_state = gmail_adapter.fetch_schedule_store.load_state()
        scheduler_state = self.gmail_fetch_scheduler_state()
        fetch_loop_active = bool(scheduler_state.get("loop_active"))
        fetch_loop_status = "active" if fetch_loop_active else "inactive"
        prompt_sync_configured = bool(self.service.state.runtime_prompt_sync_target_api_base_url)
        prompt_sync_status = "active" if (fetch_loop_active and prompt_sync_configured) else "pending" if prompt_sync_configured else "inactive"
        runtime_authorize_ready = bool(
            self.service.state.trust_state == "trusted"
            and self.service.state.node_id
            and self.service.effective_core_base_url()
        )
        runtime_authorize_status = "active" if runtime_authorize_ready else "pending"

        return [
            self.scheduled_task_entry(
                task_id="gmail_fetch_yesterday",
                title="Gmail Fetch Yesterday",
                group="gmail",
                schedule_name="daily",
                status=fetch_loop_status,
                last_execution_at=(
                    fetch_schedule_state.yesterday.last_run_at.isoformat()
                    if fetch_schedule_state is not None and fetch_schedule_state.yesterday.last_run_at is not None
                    else None
                ),
                next_execution_at=self.schedule_template_next_run("daily", local_now).isoformat(),
                last_reason=(fetch_schedule_state.yesterday.last_run_reason if fetch_schedule_state is not None else None),
                detail="Fetches the previous day inbox window for local storage refresh.",
                last_slot_key=(fetch_schedule_state.yesterday.last_slot_key if fetch_schedule_state is not None else None),
            ),
            self.scheduled_task_entry(
                task_id="gmail_fetch_today",
                title="Gmail Fetch Today",
                group="gmail",
                schedule_name="4_times_a_day",
                status=fetch_loop_status,
                last_execution_at=(
                    fetch_schedule_state.today.last_run_at.isoformat()
                    if fetch_schedule_state is not None and fetch_schedule_state.today.last_run_at is not None
                    else None
                ),
                next_execution_at=self.schedule_template_next_run("4_times_a_day", local_now).isoformat(),
                last_reason=(fetch_schedule_state.today.last_run_reason if fetch_schedule_state is not None else None),
                detail="Refreshes the current-day inbox window on the six-hour schedule.",
                last_slot_key=(fetch_schedule_state.today.last_slot_key if fetch_schedule_state is not None else None),
            ),
            self.scheduled_task_entry(
                task_id="gmail_fetch_last_hour",
                title="Gmail Fetch Last Hour",
                group="gmail",
                schedule_name="every_5_minutes",
                status=fetch_loop_status,
                last_execution_at=(
                    fetch_schedule_state.last_hour.last_run_at.isoformat()
                    if fetch_schedule_state is not None and fetch_schedule_state.last_hour.last_run_at is not None
                    else None
                ),
                next_execution_at=self.schedule_template_next_run("every_5_minutes", local_now).isoformat(),
                last_reason=(fetch_schedule_state.last_hour.last_run_reason if fetch_schedule_state is not None else None),
                detail="Keeps the rolling last-hour inbox window fresh for recent classification work.",
                last_slot_key=(fetch_schedule_state.last_hour.last_slot_key if fetch_schedule_state is not None else None),
            ),
            self.scheduled_task_entry(
                task_id="gmail_hourly_batch_classification",
                title="Hourly Batch Classification",
                group="gmail",
                schedule_name="hourly",
                status=fetch_loop_status,
                last_execution_at=(
                    self.service.state.gmail_hourly_batch_classification_last_run_at.isoformat()
                    if self.service.state.gmail_hourly_batch_classification_last_run_at is not None
                    else None
                ),
                next_execution_at=self.schedule_template_next_run("hourly", local_now).isoformat(),
                last_reason="scheduled" if self.service.state.gmail_hourly_batch_classification_last_run_at is not None else None,
                detail="Classifies the newest 100 unclassified emails and sends remaining unknowns to AI.",
                last_slot_key=self.service.state.gmail_hourly_batch_classification_slot_key,
            ),
            self.scheduled_task_entry(
                task_id="runtime_prompt_sync_weekly",
                title="Weekly Prompt Sync",
                group="runtime",
                schedule_name="weekly",
                status=prompt_sync_status,
                last_execution_at=(
                    self.service.state.runtime_prompt_sync_last_scheduled_at.isoformat()
                    if self.service.state.runtime_prompt_sync_last_scheduled_at is not None
                    else None
                ),
                next_execution_at=(
                    self.schedule_template_next_run("weekly", local_now).isoformat() if prompt_sync_configured else None
                ),
                last_reason="scheduled" if self.service.state.runtime_prompt_sync_last_scheduled_at is not None else None,
                detail=(
                    "Scans local runtime prompt JSON files and syncs them to the AI node prompt service."
                    if prompt_sync_configured
                    else "Waiting for a prompt sync target to be configured from the Runtime page."
                ),
                last_slot_key=self.service.state.runtime_prompt_sync_weekly_slot_key,
            ),
            self.scheduled_task_entry(
                task_id="runtime_monthly_resolve_authorize",
                title="Monthly Core Resolve and Authorize",
                group="runtime",
                schedule_name="monthly",
                status=runtime_authorize_status,
                last_execution_at=(
                    self.service.state.runtime_monthly_authorize_last_run_at.isoformat()
                    if self.service.state.runtime_monthly_authorize_last_run_at is not None
                    else None
                ),
                next_execution_at=(
                    self.schedule_template_next_run("monthly", local_now).isoformat() if runtime_authorize_ready else None
                ),
                last_reason="scheduled" if self.service.state.runtime_monthly_authorize_last_run_at is not None else None,
                detail=(
                    "Refreshes the Core AI service resolution and authorization grant for runtime execution."
                    if runtime_authorize_ready
                    else "Waiting for a trusted Core connection before monthly runtime authorization can run."
                ),
                last_slot_key=self.service.state.runtime_monthly_authorize_slot_key,
            ),
        ]

    async def startup(self) -> None:
        if self.service.config.gmail_status_poll_on_startup:
            self.ensure_gmail_status_polling()
        if self.service.config.gmail_fetch_poll_on_startup:
            self.ensure_gmail_fetch_polling()

    async def shutdown(self) -> None:
        await self._cancel_task(self.finalize_polling_task)
        await self._cancel_task(self.gmail_status_task)
        await self._cancel_task(self.gmail_fetch_task)

    async def _cancel_task(self, task: asyncio.Task | None) -> None:
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def cancel_finalize_polling(self) -> None:
        if self.finalize_polling_task is not None and not self.finalize_polling_task.done():
            self.finalize_polling_task.cancel()

    def ensure_finalize_polling(self) -> None:
        if self.finalize_polling_task is None or self.finalize_polling_task.done():
            self.finalize_polling_task = asyncio.create_task(self.poll_finalize_loop())

    async def poll_finalize_loop(self) -> None:
        while self.service.state.onboarding_session_id:
            correlation_id = str(uuid.uuid4())
            finalize = await self.service.core_client.finalize_onboarding(
                self.service.effective_core_base_url() or "",
                self.service.state.onboarding_session_id,
                self.service.config.node_nonce,
                correlation_id,
            )
            self.service._apply_finalize_result(finalize)
            if finalize.onboarding_status in TERMINAL_ONBOARDING_STATES:
                return
            await asyncio.sleep(self.service.config.onboarding_poll_interval_seconds)

    def ensure_gmail_status_polling(self) -> None:
        if self.gmail_status_task is None or self.gmail_status_task.done():
            GMAIL_POLL_LOGGER.info(
                "Gmail status polling loop starting",
                extra={"event_data": {"interval_seconds": self.service.config.gmail_status_poll_interval_seconds}},
            )
            self.gmail_status_task = asyncio.create_task(self.gmail_status_loop())

    def ensure_gmail_fetch_polling(self) -> None:
        if self.gmail_fetch_task is None or self.gmail_fetch_task.done():
            self.save_gmail_fetch_scheduler_state(
                loop_enabled=True,
                loop_active=True,
                status="running",
                detail="Gmail fetch scheduler loop is running.",
                last_error=None,
                last_error_at=None,
            )
            self.service.notifications.gmail_fetch_notification_state = "healthy"
            self.gmail_fetch_task = asyncio.create_task(self.gmail_fetch_loop())

    async def gmail_status_loop(self) -> None:
        while True:
            try:
                await self.refresh_gmail_status()
            except Exception as exc:
                GMAIL_POLL_LOGGER.error(
                    "Gmail status polling loop failed",
                    extra={"event_data": {"detail": str(exc)}},
                )
            await asyncio.sleep(self.service.config.gmail_status_poll_interval_seconds)

    async def refresh_gmail_status(self) -> None:
        gmail_adapter = self.service.provider_registry.get_provider("gmail")
        accounts = await gmail_adapter.list_accounts()
        eligible_accounts = [account for account in accounts if account.status in {"connected", "token_exchanged", "degraded"}]
        GMAIL_POLL_LOGGER.info(
            "Gmail status polling pass started",
            extra={"event_data": {"account_count": len(accounts), "eligible_account_count": len(eligible_accounts)}},
        )
        for account in accounts:
            if account.status in {"connected", "token_exchanged", "degraded"}:
                mailbox_status = await gmail_adapter.refresh_mailbox_status(account.account_id)
                GMAIL_POLL_LOGGER.info(
                    "Gmail status polling pass refreshed account",
                    extra={
                        "event_data": {
                            "account_id": account.account_id,
                            "checked_at": mailbox_status.checked_at.isoformat(),
                            "unread_inbox_count": mailbox_status.unread_inbox_count,
                            "unread_today_count": mailbox_status.unread_today_count,
                            "unread_last_hour_count": mailbox_status.unread_last_hour_count,
                        }
                    },
                )

    async def gmail_fetch_loop(self) -> None:
        while True:
            try:
                await self.run_due_gmail_fetches()
            except Exception as exc:
                failed_at = datetime.now(UTC).isoformat()
                self.save_gmail_fetch_scheduler_state(
                    loop_enabled=True,
                    loop_active=True,
                    status="error",
                    detail="Gmail fetch scheduler loop hit an error.",
                    last_error=str(exc),
                    last_error_at=failed_at,
                    last_checked_at=failed_at,
                )
                self.service.notifications.set_gmail_fetch_notification_state(
                    "error",
                    f"Gmail fetch scheduler failed: {exc}",
                )
                LOGGER.error("Scheduled Gmail fetch loop failed", extra={"event_data": {"detail": str(exc)}})
            try:
                await self.service._run_weekly_prompt_sync_if_due()
            except Exception as exc:
                AI_LOGGER.error("Weekly prompt sync failed", extra={"event_data": {"detail": str(exc)}})
            try:
                await self.service._run_due_monthly_runtime_authorize(datetime.now().astimezone())
            except Exception as exc:
                AI_LOGGER.error("Monthly Core resolve and authorize failed", extra={"event_data": {"detail": str(exc)}})
            await asyncio.sleep(self.seconds_until_next_minute())

    async def run_due_gmail_fetches(self) -> None:
        gmail_adapter = self.service.provider_registry.get_provider("gmail")
        if not gmail_adapter.get_enabled_status():
            self.service.notifications.set_gmail_fetch_notification_state(
                "warning",
                "Gmail fetch scheduling is paused because the Gmail provider is disabled.",
            )
            self.save_gmail_fetch_scheduler_state(
                status="idle",
                detail="Gmail fetch scheduler is idle because Gmail is disabled.",
                last_checked_at=datetime.now(UTC).isoformat(),
                last_due_windows=[],
            )
            return
        accounts = await gmail_adapter.list_accounts()
        eligible_accounts = [account for account in accounts if account.status in {"connected", "token_exchanged", "degraded"}]
        if not eligible_accounts:
            self.service.notifications.set_gmail_fetch_notification_state(
                "warning",
                "Gmail fetch scheduling is paused because no eligible Gmail account is connected.",
            )
            self.save_gmail_fetch_scheduler_state(
                status="idle",
                detail="Gmail fetch scheduler is idle because no eligible Gmail account is connected.",
                last_checked_at=datetime.now(UTC).isoformat(),
                last_due_windows=[],
            )
            return

        schedule_state = await gmail_adapter.fetch_schedule_state() if hasattr(gmail_adapter, "fetch_schedule_state") else None
        now = datetime.now().astimezone()
        due_windows = self.due_gmail_fetch_windows(now, schedule_state)
        checked_at = datetime.now(UTC).isoformat()
        self.save_gmail_fetch_scheduler_state(
            status="running" if due_windows else "idle",
            detail=(
                f"Scheduled Gmail fetch due for {', '.join(window for window, _ in due_windows)}."
                if due_windows
                else "No scheduled Gmail fetch windows are due right now."
            ),
            last_checked_at=checked_at,
            last_due_windows=[{"window": window, "slot_key": slot_key} for window, slot_key in due_windows],
        )
        self.service.notifications.set_gmail_fetch_notification_state("healthy", "Gmail fetch scheduling is running normally.")
        for account in eligible_accounts:
            for window, slot_key in due_windows:
                attempt_at = datetime.now(UTC).isoformat()
                LOGGER.info(
                    "Scheduled Gmail fetch attempt",
                    extra={"event_data": {"account_id": account.account_id, "window": window, "slot_key": slot_key}},
                )
                await self.service.providers.gmail_fetch_messages(
                    window,
                    account_id=account.account_id,
                    reason="scheduled",
                    slot_key=slot_key,
                )
                success_at = datetime.now(UTC).isoformat()
                self.save_gmail_fetch_scheduler_state(
                    status="completed",
                    detail=f"Scheduled Gmail fetch completed for {window}.",
                    last_attempt_at=attempt_at,
                    last_success_at=success_at,
                    last_error=None,
                    last_error_at=None,
                )
                LOGGER.info(
                    "Scheduled Gmail fetch completed",
                    extra={"event_data": {"account_id": account.account_id, "window": window, "slot_key": slot_key}},
                )
        await self.run_due_hourly_batch_classification(now)

    def due_gmail_fetch_windows(self, now: datetime, schedule_state) -> list[tuple[str, str]]:
        due: list[tuple[str, str]] = []
        schedule_map = {
            "yesterday": self.gmail_fetch_slot_key("yesterday", now),
            "today": self.gmail_fetch_slot_key("today", now),
            "last_hour": self.gmail_fetch_slot_key("last_hour", now),
        }
        if schedule_state is None:
            return []

        yesterday_state = getattr(schedule_state, "yesterday", None)
        if (
            schedule_map["yesterday"]
            and (now.hour > 0 or (now.hour == 0 and now.minute >= 1))
            and getattr(yesterday_state, "last_slot_key", None) != schedule_map["yesterday"]
        ):
            due.append(("yesterday", schedule_map["yesterday"]))

        today_state = getattr(schedule_state, "today", None)
        if (
            schedule_map["today"]
            and getattr(today_state, "last_slot_key", None) != schedule_map["today"]
            and now.hour // 6 == int(schedule_map["today"].rsplit(":", 1)[-1])
        ):
            due.append(("today", schedule_map["today"]))

        last_hour_state = getattr(schedule_state, "last_hour", None)
        last_hour_last_slot_key = getattr(last_hour_state, "last_slot_key", None)
        if (
            schedule_map["last_hour"]
            and last_hour_last_slot_key != schedule_map["last_hour"]
            and (
                now.minute % 5 == 0
                or last_hour_last_slot_key is not None
                or (now.minute == 1 and now.hour % 6 == 0)
            )
        ):
            due.append(("last_hour", schedule_map["last_hour"]))

        return due

    async def run_due_hourly_batch_classification(self, now: datetime) -> None:
        slot_key = self.gmail_hourly_batch_slot_key(now)
        if slot_key is None or self.service.state.gmail_hourly_batch_classification_slot_key == slot_key:
            return
        try:
            LOGGER.info("Scheduled hourly Gmail batch classification starting", extra={"event_data": {"slot_key": slot_key}})
            await self.service.runtime_execute_email_classifier_batch(
                RuntimePromptExecutionRequestInput(target_api_base_url="http://127.0.0.1:9002")
            )
            self.service.state.gmail_hourly_batch_classification_slot_key = slot_key
            self.service.state.gmail_hourly_batch_classification_last_run_at = datetime.now().astimezone()
            self.service.state_store.save(self.service.state)
            LOGGER.info("Scheduled hourly Gmail batch classification completed", extra={"event_data": {"slot_key": slot_key}})
        except Exception as exc:
            LOGGER.error(
                "Scheduled hourly Gmail batch classification failed",
                extra={"event_data": {"slot_key": slot_key, "detail": str(exc)}},
            )

    @staticmethod
    def gmail_hourly_batch_slot_key(now: datetime) -> str | None:
        local_now = now.astimezone()
        if local_now.minute >= 5:
            return None
        return local_now.replace(minute=0, second=0, microsecond=0).isoformat()

    @staticmethod
    def gmail_fetch_slot_key(window: str, now: datetime) -> str | None:
        local_now = now.astimezone()
        if window == "yesterday":
            return (local_now - timedelta(days=1)).date().isoformat()
        if window == "today":
            return f"{local_now.date().isoformat()}:{local_now.hour // 6}"
        if window == "last_hour":
            slot_time = local_now.replace(minute=(local_now.minute // 5) * 5, second=0, microsecond=0)
            return slot_time.isoformat()
        return None

    @staticmethod
    def seconds_until_next_minute() -> float:
        now = datetime.now().astimezone()
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        return max((next_minute - now).total_seconds(), 1.0)
