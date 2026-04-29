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


@dataclass(frozen=True)
class ScheduledTaskDefinition:
    task_id: str
    title: str
    kind: str
    owner: str
    schedule_name: str
    detail: str
    enabled_resolver: Callable[["BackgroundTaskManager"], bool]


class BackgroundTaskManager:
    def __init__(self, service: Any) -> None:
        self.service = service
        self.finalize_polling_task: asyncio.Task | None = None
        self.telemetry_task: asyncio.Task | None = None
        self.mqtt_health_task: asyncio.Task | None = None
        self.supervisor_heartbeat_task: asyncio.Task | None = None
        self.gmail_status_task: asyncio.Task | None = None
        self.gmail_fetch_task: asyncio.Task | None = None
        self.shipment_live_tracking_task: asyncio.Task | None = None

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

    @staticmethod
    def default_scheduler_task_state() -> dict[str, object]:
        return {
            "status": "idle",
            "enabled": False,
            "detail": "Task has not started yet.",
            "last_started_at": None,
            "last_completed_at": None,
            "last_success_at": None,
            "last_failure_at": None,
            "next_run_at": None,
            "last_error": None,
        }

    def scheduler_task_states(self) -> dict[str, dict[str, object]]:
        runtime_state = self.service.runtime.runtime_task_state()
        persisted = runtime_state.get("scheduler_task_states")
        if not isinstance(persisted, dict):
            return {}
        normalized: dict[str, dict[str, object]] = {}
        for task_id, payload in persisted.items():
            if isinstance(task_id, str) and isinstance(payload, dict):
                state = dict(self.default_scheduler_task_state())
                state.update(payload)
                normalized[task_id] = state
        return normalized

    def scheduler_task_state(self, task_id: str) -> dict[str, object]:
        state = dict(self.default_scheduler_task_state())
        state.update(self.scheduler_task_states().get(task_id, {}))
        return state

    def save_scheduler_task_state(self, task_id: str, **updates: object) -> dict[str, object]:
        all_states = self.scheduler_task_states()
        state = dict(self.default_scheduler_task_state())
        state.update(all_states.get(task_id, {}))
        state.update(updates)
        all_states[task_id] = state
        self.service.runtime.save_runtime_task_state(scheduler_task_states=all_states, updated_at=self.service.runtime.utc_iso_now())
        return state

    @classmethod
    def task_definition(cls, task_id: str) -> ScheduledTaskDefinition | None:
        for definition in cls.task_registry():
            if definition.task_id == task_id:
                return definition
        return None

    @classmethod
    def task_next_run_at(cls, task_id: str, now: datetime) -> str | None:
        definition = cls.task_definition(task_id)
        if definition is None:
            return None
        next_run = cls.schedule_template_next_run(definition.schedule_name, now.astimezone())
        return next_run.isoformat() if next_run is not None else None

    def ensure_registry_task_state(self, task_id: str, *, detail: str | None = None) -> dict[str, object]:
        definition = self.task_definition(task_id)
        if definition is None:
            return self.scheduler_task_state(task_id)
        current = self.scheduler_task_state(task_id)
        enabled = bool(definition.enabled_resolver(self))
        now = datetime.now(UTC).replace(tzinfo=None)
        if current.get("detail") == self.default_scheduler_task_state()["detail"]:
            current["detail"] = detail or definition.detail
        if current.get("status") == "idle" and not enabled:
            current["status"] = "inactive"
        current["enabled"] = enabled
        current["next_run_at"] = current.get("next_run_at") or self.task_next_run_at(task_id, now)
        return self.save_scheduler_task_state(task_id, **current)

    def provider_work_allowed(self) -> bool:
        return bool(self.service.state.trust_state == "trusted" and self.service.state.operational_readiness)

    def mark_task_running(self, task_id: str, *, detail: str, next_run_at: str | None = None) -> dict[str, object]:
        definition = self.task_definition(task_id)
        enabled = bool(definition.enabled_resolver(self)) if definition is not None else True
        now = datetime.now(UTC).replace(tzinfo=None)
        return self.save_scheduler_task_state(
            task_id,
            status="running",
            enabled=enabled,
            detail=detail,
            last_started_at=now.isoformat(),
            next_run_at=next_run_at,
            last_error=None,
        )

    def mark_task_success(
        self,
        task_id: str,
        *,
        detail: str,
        next_run_at: str | None = None,
        completed_at: datetime | None = None,
    ) -> dict[str, object]:
        definition = self.task_definition(task_id)
        enabled = bool(definition.enabled_resolver(self)) if definition is not None else True
        finished = (completed_at or datetime.now(UTC).replace(tzinfo=None)).isoformat()
        return self.save_scheduler_task_state(
            task_id,
            status="idle",
            enabled=enabled,
            detail=detail,
            last_completed_at=finished,
            last_success_at=finished,
            next_run_at=next_run_at,
            last_error=None,
        )

    def mark_task_failure(
        self,
        task_id: str,
        *,
        detail: str,
        error: str,
        next_run_at: str | None = None,
        failed_at: datetime | None = None,
    ) -> dict[str, object]:
        definition = self.task_definition(task_id)
        enabled = bool(definition.enabled_resolver(self)) if definition is not None else True
        finished = (failed_at or datetime.now(UTC).replace(tzinfo=None)).isoformat()
        return self.save_scheduler_task_state(
            task_id,
            status="failing",
            enabled=enabled,
            detail=detail,
            last_completed_at=finished,
            last_failure_at=finished,
            next_run_at=next_run_at,
            last_error=error,
        )

    def mark_task_idle(self, task_id: str, *, detail: str, next_run_at: str | None = None) -> dict[str, object]:
        definition = self.task_definition(task_id)
        enabled = bool(definition.enabled_resolver(self)) if definition is not None else True
        return self.save_scheduler_task_state(
            task_id,
            status="idle" if enabled else "inactive",
            enabled=enabled,
            detail=detail,
            next_run_at=next_run_at,
        )

    def scheduled_task_entry_from_registry(
        self,
        task_id: str,
        *,
        group: str,
        status: str,
        last_execution_at: str | None,
        next_execution_at: str | None,
        last_reason: str | None,
        detail: str,
        last_slot_key: str | None = None,
        schedule_detail: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, object]:
        definition = self.task_definition(task_id)
        if definition is None:
            raise KeyError(f"Unknown scheduler task id: {task_id}")
        return self.scheduled_task_entry(
            task_id=definition.task_id,
            title=definition.title,
            group=group,
            kind=definition.kind,
            owner=definition.owner,
            schedule_name=definition.schedule_name,
            status=status,
            enabled=bool(definition.enabled_resolver(self)) if enabled is None else enabled,
            schedule_label=schedule_detail or self.schedule_template_detail(definition.schedule_name),
            last_started_at=self.scheduler_task_state(task_id).get("last_started_at"),
            last_completed_at=self.scheduler_task_state(task_id).get("last_completed_at"),
            last_success_at=self.scheduler_task_state(task_id).get("last_success_at"),
            last_failure_at=self.scheduler_task_state(task_id).get("last_failure_at"),
            last_error=self.scheduler_task_state(task_id).get("last_error"),
            last_execution_at=last_execution_at,
            next_execution_at=next_execution_at,
            last_reason=last_reason,
            detail=detail,
            last_slot_key=last_slot_key,
            schedule_detail=schedule_detail,
        )

    @staticmethod
    def scheduled_task_public_status(value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == "active":
            return "scheduled"
        if normalized in {"inactive", "pending"}:
            return "idle"
        if normalized in {"completed", "success", "healthy"}:
            return "healthy"
        if normalized == "degraded":
            return "failing"
        if normalized in {"idle", "scheduled", "running", "failing", "stopped"}:
            return normalized
        return "idle"

    def record_heartbeat_event(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        self.save_scheduler_task_state(
            "heartbeat",
            status="running",
            enabled=bool(self.service.state.trust_state == "trusted" and self.service.state.node_id),
            detail="MQTT presence heartbeat is publishing on the configured cadence.",
            last_started_at=now.isoformat(),
            last_completed_at=now.isoformat(),
            last_success_at=now.isoformat(),
            next_run_at=(now + timedelta(seconds=self.service.config.mqtt_heartbeat_seconds)).isoformat(),
            last_error=None,
        )

    def record_mqtt_connected(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        self.save_scheduler_task_state(
            "heartbeat",
            status="running",
            enabled=bool(self.service.state.trust_state == "trusted" and self.service.state.node_id),
            detail="MQTT connection is online and heartbeat publishing is enabled.",
            last_started_at=(self.scheduler_task_state("heartbeat").get("last_started_at") or now.isoformat()),
            next_run_at=(now + timedelta(seconds=self.service.config.mqtt_heartbeat_seconds)).isoformat(),
            last_error=None,
        )

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
            "heartbeat_5_seconds": ScheduleTemplate("heartbeat_5_seconds", "Heartbeat every 5 seconds", lambda now: now + timedelta(seconds=5)),
            "every_10_seconds": ScheduleTemplate("every_10_seconds", "Every 10 seconds", lambda now: now + timedelta(seconds=10)),
            "telemetry_60_seconds": ScheduleTemplate("telemetry_60_seconds", "Telemetry every 60 seconds", lambda now: now + timedelta(seconds=60)),
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
            "interval_seconds": ScheduleTemplate("interval_seconds", "Every N seconds (requires integer seconds)", lambda now: None),
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

    @staticmethod
    def schedule_template_sort_key(name: str) -> tuple[int, str]:
        order = {
            "heartbeat_5_seconds": 5,
            "every_10_seconds": 10,
            "telemetry_60_seconds": 15,
            "every_5_minutes": 20,
            "hourly": 30,
            "4_times_a_day": 40,
            "daily": 50,
            "every_other_day": 60,
            "twice_a_week": 70,
            "weekly": 80,
            "bi_weekly": 90,
            "monthly": 100,
            "on_start": 110,
            "interval_seconds": 999,
        }
        return (order.get(name, 500), name)

    @classmethod
    def scheduled_task_entry(
        cls,
        *,
        task_id: str,
        title: str,
        group: str,
        kind: str | None = None,
        owner: str | None = None,
        schedule_name: str,
        status: str,
        enabled: bool,
        schedule_label: str | None,
        last_started_at: str | None,
        last_completed_at: str | None,
        last_success_at: str | None,
        last_failure_at: str | None,
        last_error: str | None,
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
            "kind": kind or group,
            "owner": owner or group,
            "schedule_name": schedule_name,
            "schedule_detail": schedule_detail or cls.schedule_template_detail(schedule_name),
            "schedule_label": schedule_label or schedule_detail or cls.schedule_template_detail(schedule_name),
            "status": status,
            "enabled": enabled,
            "last_started_at": last_started_at,
            "last_completed_at": last_completed_at,
            "last_success_at": last_success_at,
            "last_failure_at": last_failure_at,
            "last_error": last_error,
            "last_execution_at": last_execution_at,
            "next_execution_at": next_execution_at,
            "last_reason": last_reason,
            "detail": detail,
            "last_slot_key": last_slot_key,
        }

    @classmethod
    def scheduled_task_legend(cls) -> list[dict[str, str]]:
        return [
            {"name": template.name, "detail": template.detail}
            for template in sorted(cls.schedule_templates().values(), key=lambda item: cls.schedule_template_sort_key(item.name))
        ]

    @classmethod
    def task_registry(cls) -> tuple[ScheduledTaskDefinition, ...]:
        return (
            ScheduledTaskDefinition(
                task_id="heartbeat",
                title="Heartbeat",
                kind="node_local_recurring_work",
                owner="mqtt_manager",
                schedule_name="heartbeat_5_seconds",
                detail="Publishes MQTT presence heartbeats for node liveness and freshness tracking.",
                enabled_resolver=lambda manager: bool(manager.service.state.trust_state == "trusted" and manager.service.state.node_id),
            ),
            ScheduledTaskDefinition(
                task_id="telemetry",
                title="Telemetry",
                kind="node_local_recurring_work",
                owner="background_task_manager",
                schedule_name="telemetry_60_seconds",
                detail="Refreshes baseline runtime telemetry state for operator-visible scheduler status.",
                enabled_resolver=lambda manager: True,
            ),
            ScheduledTaskDefinition(
                task_id="supervisor_heartbeat",
                title="Supervisor Heartbeat",
                kind="node_local_recurring_work",
                owner="background_task_manager",
                schedule_name="heartbeat_5_seconds",
                detail="Registers with Supervisor and publishes runtime heartbeats on the 5-second cadence.",
                enabled_resolver=lambda manager: True,
            ),
            ScheduledTaskDefinition(
                task_id="operational_mqtt_health",
                title="Operational MQTT Health",
                kind="node_local_recurring_work",
                owner="background_task_manager",
                schedule_name="every_10_seconds",
                detail="Monitors operational MQTT freshness and health on the standard baseline cadence.",
                enabled_resolver=lambda manager: True,
            ),
            ScheduledTaskDefinition(
                task_id="onboarding_finalize_polling",
                title="Onboarding Finalize Polling",
                kind="node_local_recurring_work",
                owner="background_task_manager",
                schedule_name="interval_seconds",
                detail="Polls Core finalize state while onboarding approval is pending.",
                enabled_resolver=lambda manager: bool(manager.service.state.onboarding_session_id),
            ),
            ScheduledTaskDefinition(
                task_id="gmail_status_polling",
                title="Gmail Status Polling",
                kind="provider_recurring_work",
                owner="background_task_manager",
                schedule_name="interval_seconds",
                detail="Refreshes Gmail mailbox status for connected accounts on the configured status interval.",
                enabled_resolver=lambda manager: bool(manager.service.config.gmail_status_poll_on_startup),
            ),
            ScheduledTaskDefinition(
                task_id="gmail_fetch_yesterday",
                title="Gmail Fetch Yesterday",
                kind="provider_recurring_work",
                owner="background_task_manager",
                schedule_name="daily",
                detail="Fetches the previous day inbox window for local storage refresh.",
                enabled_resolver=lambda manager: bool(manager.service.config.gmail_fetch_poll_on_startup),
            ),
            ScheduledTaskDefinition(
                task_id="gmail_fetch_today",
                title="Gmail Fetch Today",
                kind="provider_recurring_work",
                owner="background_task_manager",
                schedule_name="4_times_a_day",
                detail="Refreshes the current-day inbox window on the six-hour schedule.",
                enabled_resolver=lambda manager: bool(manager.service.config.gmail_fetch_poll_on_startup),
            ),
            ScheduledTaskDefinition(
                task_id="gmail_fetch_last_hour",
                title="Gmail Fetch Last Hour",
                kind="provider_recurring_work",
                owner="background_task_manager",
                schedule_name="every_5_minutes",
                detail="Keeps the rolling last-hour inbox window fresh for recent classification work.",
                enabled_resolver=lambda manager: bool(manager.service.config.gmail_fetch_poll_on_startup),
            ),
            ScheduledTaskDefinition(
                task_id="gmail_hourly_batch_classification",
                title="5-Minute Batch Classification",
                kind="node_local_recurring_work",
                owner="background_task_manager",
                schedule_name="every_5_minutes",
                detail="Classifies the newest 100 unclassified emails and sends remaining unknowns to AI.",
                enabled_resolver=lambda manager: bool(manager.service.config.gmail_fetch_poll_on_startup),
            ),
            ScheduledTaskDefinition(
                task_id="shipment_live_tracking_refresh",
                title="Shipment Live Tracking Refresh",
                kind="provider_recurring_work",
                owner="background_task_manager",
                schedule_name="every_5_minutes",
                detail="Refreshes Track123 live tracking status for all enabled shipment records.",
                enabled_resolver=lambda manager: bool(
                    manager.provider_work_allowed()
                    and manager.service.config.track123_enabled
                    and manager.service.config.track123_api_secret
                ),
            ),
            ScheduledTaskDefinition(
                task_id="runtime_prompt_sync_weekly",
                title="Weekly Prompt Sync",
                kind="node_local_recurring_work",
                owner="background_task_manager",
                schedule_name="weekly",
                detail="Scans local runtime prompt JSON files and syncs them to the AI node prompt service.",
                enabled_resolver=lambda manager: bool(manager.service.state.runtime_prompt_sync_target_api_base_url),
            ),
            ScheduledTaskDefinition(
                task_id="runtime_monthly_resolve_authorize",
                title="Monthly Core Resolve and Authorize",
                kind="core_leased_recurring_work",
                owner="background_task_manager",
                schedule_name="monthly",
                detail="Refreshes the Core AI service resolution and authorization grant for runtime execution.",
                enabled_resolver=lambda manager: bool(
                    manager.service.state.trust_state == "trusted"
                    and manager.service.state.node_id
                    and manager.service.effective_core_base_url()
                ),
            ),
        )

    def scheduled_tasks_snapshot(self) -> list[dict[str, object]]:
        local_now = datetime.now().astimezone()
        heartbeat_state = self.scheduler_task_state("heartbeat")
        telemetry_state = self.scheduler_task_state("telemetry")
        mqtt_health_state = self.scheduler_task_state("operational_mqtt_health")
        mqtt_health = self.service._mqtt_health_snapshot()
        fetch_schedule_state = None
        gmail_adapter = self.service.provider_registry.get_provider("gmail")
        if hasattr(gmail_adapter, "fetch_schedule_state"):
            fetch_schedule_state = gmail_adapter.fetch_schedule_store.load_state()
        scheduler_state = self.gmail_fetch_scheduler_state()
        fetch_loop_active = bool(scheduler_state.get("loop_active"))
        fetch_loop_status = "scheduled" if fetch_loop_active else "idle"
        finalize_active = bool(self.finalize_polling_task is not None and not self.finalize_polling_task.done())
        gmail_status_active = bool(self.gmail_status_task is not None and not self.gmail_status_task.done())
        prompt_sync_configured = bool(self.service.state.runtime_prompt_sync_target_api_base_url)
        prompt_sync_status = "scheduled" if (fetch_loop_active and prompt_sync_configured) else "idle"
        runtime_authorize_ready = bool(
            self.service.state.trust_state == "trusted"
            and self.service.state.node_id
            and self.service.effective_core_base_url()
        )
        runtime_authorize_status = "scheduled" if runtime_authorize_ready else "idle"
        live_tracking_state = self.scheduler_task_state("shipment_live_tracking_refresh")
        live_tracking_ready = bool(
            self.provider_work_allowed()
            and self.service.config.track123_enabled
            and self.service.config.track123_api_secret
        )

        return [
            self.scheduled_task_entry_from_registry(
                "heartbeat",
                group="runtime",
                status=self.scheduled_task_public_status(
                    heartbeat_state.get("status") or ("healthy" if self.service.mqtt_manager.status.state == "connected" else "idle")
                ),
                last_execution_at=heartbeat_state.get("last_success_at"),
                next_execution_at=heartbeat_state.get("next_run_at"),
                last_reason=None,
                detail=str(heartbeat_state.get("detail") or "Publishes MQTT presence heartbeats for node liveness and freshness tracking."),
                schedule_detail="Heartbeat every 5 seconds",
                enabled=bool(heartbeat_state.get("enabled")),
            ),
            self.scheduled_task_entry_from_registry(
                "telemetry",
                group="runtime",
                status=self.scheduled_task_public_status(telemetry_state.get("status") or "idle"),
                last_execution_at=telemetry_state.get("last_success_at") or telemetry_state.get("last_started_at"),
                next_execution_at=telemetry_state.get("next_run_at"),
                last_reason=None,
                detail=str(telemetry_state.get("detail") or "Refreshes baseline runtime telemetry state for operator-visible scheduler status."),
                schedule_detail="Telemetry every 60 seconds",
                enabled=bool(telemetry_state.get("enabled")),
            ),
            self.scheduled_task_entry_from_registry(
                "operational_mqtt_health",
                group="runtime",
                status=self.scheduled_task_public_status(mqtt_health_state.get("status") or "idle"),
                last_execution_at=mqtt_health_state.get("last_success_at") or mqtt_health_state.get("last_started_at"),
                next_execution_at=mqtt_health_state.get("next_run_at"),
                last_reason=None,
                detail=str(
                    mqtt_health_state.get("detail")
                    or f"MQTT health is {mqtt_health.health_status} with freshness {mqtt_health.status_freshness_state}."
                ),
                schedule_detail=(
                    "Every 10 seconds while degraded or during recovery windows; every 5 minutes while stable."
                ),
                enabled=bool(mqtt_health_state.get("enabled")),
            ),
            self.scheduled_task_entry_from_registry(
                "onboarding_finalize_polling",
                group="runtime",
                status="running" if finalize_active else "idle",
                last_execution_at=(self.service.state.last_poll_at.isoformat() if self.service.state.last_poll_at is not None else None),
                next_execution_at=None,
                last_reason=self.service.state.last_finalize_status,
                detail="Polls Core finalize state while onboarding approval is pending.",
                schedule_detail=f"Every {self.service.config.onboarding_poll_interval_seconds:g} seconds",
                enabled=bool(self.service.state.onboarding_session_id),
            ),
            self.scheduled_task_entry_from_registry(
                "gmail_status_polling",
                group="gmail",
                status="scheduled" if gmail_status_active else "idle",
                last_execution_at=None,
                next_execution_at=None,
                last_reason=None,
                detail="Refreshes Gmail mailbox status for connected accounts on the configured status interval.",
                schedule_detail=f"Every {self.service.config.gmail_status_poll_interval_seconds:g} seconds",
                enabled=bool(self.service.config.gmail_status_poll_on_startup),
            ),
            self.scheduled_task_entry_from_registry(
                "gmail_fetch_yesterday",
                group="gmail",
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
                enabled=bool(self.service.config.gmail_fetch_poll_on_startup),
            ),
            self.scheduled_task_entry_from_registry(
                "gmail_fetch_today",
                group="gmail",
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
                enabled=bool(self.service.config.gmail_fetch_poll_on_startup),
            ),
            self.scheduled_task_entry_from_registry(
                "gmail_fetch_last_hour",
                group="gmail",
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
                enabled=bool(self.service.config.gmail_fetch_poll_on_startup),
            ),
            self.scheduled_task_entry_from_registry(
                "gmail_hourly_batch_classification",
                group="gmail",
                status=fetch_loop_status,
                last_execution_at=(
                    self.service.state.gmail_hourly_batch_classification_last_run_at.isoformat()
                    if self.service.state.gmail_hourly_batch_classification_last_run_at is not None
                    else None
                ),
                next_execution_at=self.schedule_template_next_run("every_5_minutes", local_now).isoformat(),
                last_reason="scheduled" if self.service.state.gmail_hourly_batch_classification_last_run_at is not None else None,
                detail="Classifies the newest 100 unclassified emails and sends remaining unknowns to AI.",
                last_slot_key=self.service.state.gmail_hourly_batch_classification_slot_key,
                enabled=bool(self.service.config.gmail_fetch_poll_on_startup),
            ),
            self.scheduled_task_entry_from_registry(
                "shipment_live_tracking_refresh",
                group="shipments",
                status=self.scheduled_task_public_status(live_tracking_state.get("status") or ("scheduled" if live_tracking_ready else "idle")),
                last_execution_at=live_tracking_state.get("last_success_at") or live_tracking_state.get("last_started_at"),
                next_execution_at=(
                    live_tracking_state.get("next_run_at")
                    or (self.schedule_template_next_run("every_5_minutes", local_now).isoformat() if live_tracking_ready else None)
                ),
                last_reason="scheduled" if live_tracking_state.get("last_success_at") else None,
                detail=str(
                    live_tracking_state.get("detail")
                    or (
                        "Refreshes Track123 live tracking status for enabled shipment records."
                        if live_tracking_ready
                        else "Waiting for trusted readiness and Track123 configuration."
                    )
                ),
                last_slot_key=live_tracking_state.get("last_slot_key"),
                enabled=live_tracking_ready,
            ),
            self.scheduled_task_entry_from_registry(
                "runtime_prompt_sync_weekly",
                group="runtime",
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
                enabled=prompt_sync_configured,
            ),
            self.scheduled_task_entry_from_registry(
                "runtime_monthly_resolve_authorize",
                group="runtime",
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
                enabled=runtime_authorize_ready,
            ),
        ]

    async def startup(self) -> None:
        for definition in self.task_registry():
            self.ensure_registry_task_state(definition.task_id)
        self.ensure_telemetry_polling()
        self.ensure_mqtt_health_polling()
        self.ensure_supervisor_heartbeat_polling()
        self.sync_runtime_task_gating()

    async def shutdown(self) -> None:
        await self._cancel_task(self.finalize_polling_task)
        await self._cancel_task(self.telemetry_task)
        await self._cancel_task(self.mqtt_health_task)
        await self._cancel_task(self.supervisor_heartbeat_task)
        await self._cancel_task(self.gmail_status_task)
        await self._cancel_task(self.gmail_fetch_task)
        await self._cancel_task(self.shipment_live_tracking_task)
        for task_id in (
            "telemetry",
            "supervisor_heartbeat",
            "operational_mqtt_health",
            "gmail_status_polling",
            "gmail_fetch_yesterday",
            "gmail_fetch_today",
            "gmail_fetch_last_hour",
            "gmail_hourly_batch_classification",
            "shipment_live_tracking_refresh",
        ):
            self.save_scheduler_task_state(task_id, status="stopped", detail="Task stopped during scheduler shutdown.", next_run_at=None)

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
            self.mark_task_running("onboarding_finalize_polling", detail="Onboarding finalize polling loop is running.")
            self.finalize_polling_task = asyncio.create_task(self.poll_finalize_loop())

    def sync_runtime_task_gating(self) -> None:
        if self.provider_work_allowed():
            if self.service.config.gmail_status_poll_on_startup:
                self.ensure_gmail_status_polling()
            if self.service.config.gmail_fetch_poll_on_startup:
                self.ensure_gmail_fetch_polling()
            if self.service.config.track123_enabled and self.service.config.track123_api_secret:
                self.ensure_shipment_live_tracking_polling()
            else:
                if self.shipment_live_tracking_task is not None and not self.shipment_live_tracking_task.done():
                    self.shipment_live_tracking_task.cancel()
                self.mark_task_idle("shipment_live_tracking_refresh", detail="Shipment live tracking refresh is waiting for Track123 configuration.")
            return

        if self.gmail_status_task is not None and not self.gmail_status_task.done():
            self.gmail_status_task.cancel()
        if self.gmail_fetch_task is not None and not self.gmail_fetch_task.done():
            self.gmail_fetch_task.cancel()
        if self.shipment_live_tracking_task is not None and not self.shipment_live_tracking_task.done():
            self.shipment_live_tracking_task.cancel()
        blocked_detail = "Provider recurring work is waiting for trusted operational readiness."
        self.mark_task_idle("gmail_status_polling", detail=blocked_detail)
        self.mark_task_idle("gmail_fetch_yesterday", detail=blocked_detail)
        self.mark_task_idle("gmail_fetch_today", detail=blocked_detail)
        self.mark_task_idle("gmail_fetch_last_hour", detail=blocked_detail)
        self.mark_task_idle("gmail_hourly_batch_classification", detail=blocked_detail)
        self.mark_task_idle("shipment_live_tracking_refresh", detail=blocked_detail)

    def ensure_telemetry_polling(self) -> None:
        if self.telemetry_task is None or self.telemetry_task.done():
            now = datetime.now(UTC).replace(tzinfo=None)
            self.save_scheduler_task_state(
                "telemetry",
                status="running",
                enabled=True,
                detail="Telemetry loop is starting.",
                last_started_at=now.isoformat(),
                next_run_at=(now + timedelta(seconds=60)).isoformat(),
                last_error=None,
            )
            self.telemetry_task = asyncio.create_task(self.telemetry_loop())

    def ensure_mqtt_health_polling(self) -> None:
        if self.mqtt_health_task is None or self.mqtt_health_task.done():
            now = datetime.now(UTC).replace(tzinfo=None)
            self.save_scheduler_task_state(
                "operational_mqtt_health",
                status="running",
                enabled=True,
                detail="Operational MQTT health loop is starting.",
                last_started_at=now.isoformat(),
                next_run_at=(now + timedelta(seconds=self.mqtt_health_poll_interval_seconds())).isoformat(),
                last_error=None,
            )
            self.mqtt_health_task = asyncio.create_task(self.mqtt_health_loop())

    def ensure_supervisor_heartbeat_polling(self) -> None:
        if self.supervisor_heartbeat_task is None or self.supervisor_heartbeat_task.done():
            now = datetime.now(UTC).replace(tzinfo=None)
            self.save_scheduler_task_state(
                "supervisor_heartbeat",
                status="running",
                enabled=True,
                detail="Supervisor heartbeat loop is starting.",
                last_started_at=now.isoformat(),
                next_run_at=(now + timedelta(seconds=5)).isoformat(),
                last_error=None,
            )
            self.supervisor_heartbeat_task = asyncio.create_task(self.supervisor_heartbeat_loop())

    async def telemetry_loop(self) -> None:
        while True:
            now = datetime.now(UTC).replace(tzinfo=None)
            self.save_scheduler_task_state(
                "telemetry",
                status="running",
                enabled=True,
                detail=(
                    f"Runtime telemetry refreshed; trust={self.service.state.trust_state}, "
                    f"readiness={self.service.state.operational_readiness}, mqtt={self.service.mqtt_manager.status.state}."
                ),
                last_started_at=now.isoformat(),
                last_completed_at=now.isoformat(),
                last_success_at=now.isoformat(),
                next_run_at=(now + timedelta(seconds=60)).isoformat(),
                last_error=None,
            )
            await asyncio.sleep(60)

    async def supervisor_heartbeat_loop(self) -> None:
        while True:
            now = datetime.now(UTC).replace(tzinfo=None)
            result = await self.service.supervisor_heartbeat_once()
            status = "running"
            detail = "Supervisor heartbeat published."
            if isinstance(result, dict):
                if result.get("status") == "skipped":
                    detail = f"Supervisor heartbeat skipped: {result.get('reason')}"
                elif result.get("status") == "error":
                    status = "failing"
                    detail = f"Supervisor heartbeat error: {result.get('reason')}"
            self.save_scheduler_task_state(
                "supervisor_heartbeat",
                status=status,
                enabled=True,
                detail=detail,
                last_started_at=now.isoformat(),
                last_completed_at=now.isoformat(),
                last_success_at=now.isoformat() if status == "running" else self.scheduler_task_state("supervisor_heartbeat").get("last_success_at"),
                last_failure_at=now.isoformat() if status == "failing" else self.scheduler_task_state("supervisor_heartbeat").get("last_failure_at"),
                next_run_at=(now + timedelta(seconds=5)).isoformat(),
                last_error=None if status == "running" else str(result),
            )
            await asyncio.sleep(5)

    def mqtt_health_poll_interval_seconds(self) -> int:
        now = datetime.now(UTC).replace(tzinfo=None)
        created_at = self.service.state.created_at.replace(tzinfo=None) if self.service.state.created_at.tzinfo else self.service.state.created_at
        startup_age_s = max(0, int((now - created_at).total_seconds()))
        health = self.service._mqtt_health_snapshot()
        if startup_age_s < 300:
            return 10
        if self.service.state.trust_state != "trusted":
            return 10
        if not self.service.state.operational_readiness:
            return 10
        if health.health_status != "connected" or health.status_freshness_state != "fresh":
            return 10
        return 300

    async def mqtt_health_loop(self) -> None:
        while True:
            now = datetime.now(UTC).replace(tzinfo=None)
            health = self.service._mqtt_health_snapshot()
            interval_seconds = self.mqtt_health_poll_interval_seconds()
            status = "running"
            if health.health_status == "offline":
                status = "failing"
            elif health.health_status != "connected" or health.status_freshness_state != "fresh":
                status = "degraded"
            self.save_scheduler_task_state(
                "operational_mqtt_health",
                status=status,
                enabled=True,
                detail=(
                    f"MQTT health={health.health_status}; freshness={health.status_freshness_state}; "
                    f"last_report_at={health.last_status_report_at.isoformat() if health.last_status_report_at is not None else 'none'}."
                ),
                last_started_at=now.isoformat(),
                last_completed_at=now.isoformat(),
                last_success_at=now.isoformat() if status == "running" else self.scheduler_task_state("operational_mqtt_health").get("last_success_at"),
                last_failure_at=now.isoformat() if status == "failing" else self.scheduler_task_state("operational_mqtt_health").get("last_failure_at"),
                next_run_at=(now + timedelta(seconds=interval_seconds)).isoformat(),
                last_error=(None if status == "running" else f"MQTT health is {health.health_status} / {health.status_freshness_state}"),
            )
            await asyncio.sleep(interval_seconds)

    async def poll_finalize_loop(self) -> None:
        while self.service.state.onboarding_session_id:
            correlation_id = str(uuid.uuid4())
            self.mark_task_running("onboarding_finalize_polling", detail="Polling Core for onboarding finalize status.")
            finalize = await self.service.core_client.finalize_onboarding(
                self.service.effective_core_base_url() or "",
                self.service.state.onboarding_session_id,
                self.service.config.node_nonce,
                correlation_id,
            )
            self.service._apply_finalize_result(finalize)
            self.mark_task_success(
                "onboarding_finalize_polling",
                detail=f"Last finalize poll returned onboarding status {finalize.onboarding_status}.",
            )
            if finalize.onboarding_status in TERMINAL_ONBOARDING_STATES:
                self.mark_task_idle(
                    "onboarding_finalize_polling",
                    detail=f"Finalize polling stopped because onboarding status is {finalize.onboarding_status}.",
                )
                return
            await asyncio.sleep(self.service.config.onboarding_poll_interval_seconds)

    def ensure_gmail_status_polling(self) -> None:
        if self.gmail_status_task is None or self.gmail_status_task.done():
            self.mark_task_running(
                "gmail_status_polling",
                detail="Gmail status polling loop is running.",
                next_run_at=(datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.service.config.gmail_status_poll_interval_seconds)).isoformat(),
            )
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

    def ensure_shipment_live_tracking_polling(self) -> None:
        if self.shipment_live_tracking_task is None or self.shipment_live_tracking_task.done():
            now = datetime.now(UTC).replace(tzinfo=None)
            self.save_scheduler_task_state(
                "shipment_live_tracking_refresh",
                status="scheduled",
                enabled=True,
                detail="Shipment live tracking refresh loop is running.",
                last_started_at=now.isoformat(),
                next_run_at=self.schedule_template_next_run("every_5_minutes", now.astimezone()).isoformat(),
                last_error=None,
            )
            self.shipment_live_tracking_task = asyncio.create_task(self.shipment_live_tracking_loop())

    async def gmail_status_loop(self) -> None:
        while True:
            try:
                await self.refresh_gmail_status()
            except Exception as exc:
                self.mark_task_failure(
                    "gmail_status_polling",
                    detail="Gmail status polling loop failed.",
                    error=str(exc),
                    next_run_at=(datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.service.config.gmail_status_poll_interval_seconds)).isoformat(),
                )
                GMAIL_POLL_LOGGER.error(
                    "Gmail status polling loop failed",
                    extra={"event_data": {"detail": str(exc)}},
                )
            await asyncio.sleep(self.service.config.gmail_status_poll_interval_seconds)

    async def refresh_gmail_status(self) -> None:
        gmail_adapter = self.service.provider_registry.get_provider("gmail")
        accounts = await gmail_adapter.list_accounts()
        eligible_accounts = [account for account in accounts if account.status in {"connected", "token_exchanged", "degraded"}]
        if not self.service._runtime_provider_calls_enabled():
            self.mark_task_idle(
                "gmail_status_polling",
                detail="Gmail status polling is paused because provider calls are disabled.",
                next_run_at=(datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.service.config.gmail_status_poll_interval_seconds)).isoformat(),
            )
            GMAIL_POLL_LOGGER.info(
                "Gmail status polling pass skipped because provider calls are disabled",
                extra={"event_data": {"account_count": len(accounts)}},
            )
            return
        GMAIL_POLL_LOGGER.info(
            "Gmail status polling pass started",
            extra={"event_data": {"account_count": len(accounts), "eligible_account_count": len(eligible_accounts)}},
        )
        self.mark_task_running(
            "gmail_status_polling",
            detail=f"Refreshing Gmail mailbox status for {len(eligible_accounts)} eligible account(s).",
            next_run_at=(datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.service.config.gmail_status_poll_interval_seconds)).isoformat(),
        )
        for account in accounts:
            if account.status in {"connected", "token_exchanged", "degraded"}:
                mailbox_status = await self.service.email_provider_gateway.gmail_refresh_mailbox_status(account.account_id)
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
        self.mark_task_success(
            "gmail_status_polling",
            detail=f"Gmail status polling refreshed {len(eligible_accounts)} eligible account(s).",
            next_run_at=(datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.service.config.gmail_status_poll_interval_seconds)).isoformat(),
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

    async def shipment_live_tracking_loop(self) -> None:
        while True:
            try:
                await self.run_due_shipment_live_tracking_refresh(datetime.now().astimezone())
            except Exception as exc:
                now = datetime.now().astimezone()
                self.mark_task_failure(
                    "shipment_live_tracking_refresh",
                    detail="Scheduled shipment live tracking refresh failed.",
                    error=str(exc),
                    next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
                )
                LOGGER.error("Scheduled shipment live tracking refresh failed", extra={"event_data": {"detail": str(exc)}})
            await asyncio.sleep(self.seconds_until_next_minute())

    async def run_due_shipment_live_tracking_refresh(self, now: datetime) -> dict[str, object] | None:
        slot_key = self.gmail_hourly_batch_slot_key(now)
        current_task_state = self.scheduler_task_state("shipment_live_tracking_refresh")
        if slot_key is None or current_task_state.get("last_slot_key") == slot_key:
            self.mark_task_idle(
                "shipment_live_tracking_refresh",
                detail="Waiting for the next 5-minute shipment tracking refresh slot.",
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
            return None
        if not self.provider_work_allowed():
            self.mark_task_idle(
                "shipment_live_tracking_refresh",
                detail="Shipment live tracking refresh is waiting for trusted operational readiness.",
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
            return None
        if not self.service.config.track123_enabled or not self.service.config.track123_api_secret:
            self.mark_task_idle(
                "shipment_live_tracking_refresh",
                detail="Shipment live tracking refresh is waiting for Track123 configuration.",
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
            return None
        if current_task_state.get("status") == "running":
            LOGGER.info(
                "Scheduled shipment live tracking refresh skipped because the previous run is still active",
                extra={"event_data": {"slot_key": slot_key, "active_detail": current_task_state.get("detail")}},
            )
            return None
        self.mark_task_running(
            "shipment_live_tracking_refresh",
            detail=f"Scheduled shipment live tracking refresh is running for 5-minute slot {slot_key}.",
            next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
        )
        LOGGER.info("Scheduled shipment live tracking refresh starting", extra={"event_data": {"slot_key": slot_key}})
        result = await self.service.refresh_all_shipment_live_tracking()
        detail = (
            f"Scheduled shipment live tracking refreshed {result.get('refreshed', 0)} of "
            f"{result.get('total', 0)} enabled record(s); failures={result.get('failed', 0)}."
        )
        if result.get("failed"):
            self.mark_task_failure(
                "shipment_live_tracking_refresh",
                detail=detail,
                error=detail,
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
        else:
            self.mark_task_success(
                "shipment_live_tracking_refresh",
                detail=detail,
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
        state = self.scheduler_task_state("shipment_live_tracking_refresh")
        self.save_scheduler_task_state("shipment_live_tracking_refresh", **{**state, "last_slot_key": slot_key})
        LOGGER.info("Scheduled shipment live tracking refresh completed", extra={"event_data": {"slot_key": slot_key, **result}})
        return result

    async def run_due_gmail_fetches(self) -> None:
        gmail_adapter = self.service.provider_registry.get_provider("gmail")
        if not gmail_adapter.get_enabled_status():
            self.service.notifications.set_gmail_fetch_notification_state(
                "warning",
                "Gmail fetch scheduling is paused because the Gmail provider is disabled.",
            )
            for task_id in ("gmail_fetch_yesterday", "gmail_fetch_today", "gmail_fetch_last_hour"):
                self.mark_task_idle(task_id, detail="Gmail fetch scheduling is paused because Gmail is disabled.")
            self.save_gmail_fetch_scheduler_state(
                status="idle",
                detail="Gmail fetch scheduler is idle because Gmail is disabled.",
                last_checked_at=datetime.now(UTC).isoformat(),
                last_due_windows=[],
            )
            return
        if not self.service._runtime_provider_calls_enabled():
            self.service.notifications.set_gmail_fetch_notification_state(
                "warning",
                "Gmail fetch scheduling is paused because provider calls are disabled.",
            )
            for task_id in ("gmail_fetch_yesterday", "gmail_fetch_today", "gmail_fetch_last_hour"):
                self.mark_task_idle(task_id, detail="Gmail fetch scheduling is paused because provider calls are disabled.")
            self.save_gmail_fetch_scheduler_state(
                status="idle",
                detail="Gmail fetch scheduler is idle because provider calls are disabled.",
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
            for task_id in ("gmail_fetch_yesterday", "gmail_fetch_today", "gmail_fetch_last_hour"):
                self.mark_task_idle(task_id, detail="Gmail fetch scheduling is paused because no eligible Gmail account is connected.")
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
        for task_id, schedule_name in (
            ("gmail_fetch_yesterday", "daily"),
            ("gmail_fetch_today", "4_times_a_day"),
            ("gmail_fetch_last_hour", "every_5_minutes"),
        ):
            self.mark_task_idle(
                task_id,
                detail="Waiting for the next due fetch window.",
                next_run_at=self.schedule_template_next_run(schedule_name, now).isoformat(),
            )
        self.service.notifications.set_gmail_fetch_notification_state("healthy", "Gmail fetch scheduling is running normally.")
        for account in eligible_accounts:
            for window, slot_key in due_windows:
                task_id = f"gmail_fetch_{window}"
                attempt_at = datetime.now(UTC).isoformat()
                schedule_name = "daily" if window == "yesterday" else "4_times_a_day" if window == "today" else "every_5_minutes"
                self.mark_task_running(
                    task_id,
                    detail=f"Scheduled Gmail fetch running for {window} on account {account.account_id}.",
                    next_run_at=self.schedule_template_next_run(schedule_name, now).isoformat(),
                )
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
                self.mark_task_success(
                    task_id,
                    detail=f"Scheduled Gmail fetch completed for {window}.",
                    next_run_at=self.schedule_template_next_run(schedule_name, now).isoformat(),
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
        current_task_state = self.scheduler_task_state("gmail_hourly_batch_classification")
        if current_task_state.get("status") == "running":
            LOGGER.info(
                "Scheduled Gmail batch classification skipped because the previous run is still active",
                extra={"event_data": {"slot_key": slot_key, "active_detail": current_task_state.get("detail")}},
            )
            return
        try:
            self.service.state.gmail_hourly_batch_classification_slot_key = slot_key
            self.service.state_store.save(self.service.state)
            self.mark_task_running(
                "gmail_hourly_batch_classification",
                detail=f"Scheduled Gmail batch classification is running for 5-minute slot {slot_key}.",
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
            LOGGER.info("Scheduled Gmail batch classification starting", extra={"event_data": {"slot_key": slot_key}})
            await self.service.runtime_execute_email_classifier_batch(
                RuntimePromptExecutionRequestInput(target_api_base_url="http://127.0.0.1:9002")
            )
            self.service.state.gmail_hourly_batch_classification_last_run_at = datetime.now().astimezone()
            self.service.state_store.save(self.service.state)
            self.mark_task_success(
                "gmail_hourly_batch_classification",
                detail=f"Scheduled Gmail batch classification completed for 5-minute slot {slot_key}.",
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
            LOGGER.info("Scheduled Gmail batch classification completed", extra={"event_data": {"slot_key": slot_key}})
        except Exception as exc:
            self.mark_task_failure(
                "gmail_hourly_batch_classification",
                detail=f"Scheduled Gmail batch classification failed for 5-minute slot {slot_key}.",
                error=str(exc),
                next_run_at=self.schedule_template_next_run("every_5_minutes", now).isoformat(),
            )
            LOGGER.error(
                "Scheduled Gmail batch classification failed",
                extra={"event_data": {"slot_key": slot_key, "detail": str(exc)}},
            )

    @staticmethod
    def gmail_hourly_batch_slot_key(now: datetime) -> str | None:
        local_now = now.astimezone()
        slot_minute = local_now.minute - (local_now.minute % 5)
        return local_now.replace(minute=slot_minute, second=0, microsecond=0).isoformat()

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
