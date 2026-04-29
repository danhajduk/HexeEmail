from __future__ import annotations

import pytest

from service import NodeService
from node_backend.scheduler import BackgroundTaskManager
from tests.helpers import FakeMQTTManager, build_core_app


def test_scheduler_legend_is_sorted_with_interval_last():
    legend = NodeService._scheduled_task_legend()
    names = [item["name"] for item in legend]

    assert names.index("heartbeat_5_seconds") < names.index("every_10_seconds")
    assert names.index("every_10_seconds") < names.index("every_5_minutes")
    assert names.index("telemetry_60_seconds") < names.index("every_5_minutes")
    assert names.index("every_5_minutes") < names.index("hourly")
    assert names.index("hourly") < names.index("daily")
    assert names[-1] == "interval_seconds"


@pytest.mark.asyncio
async def test_scheduler_startup_initializes_persisted_task_state(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    await service.start()

    scheduler_states = service.runtime.runtime_task_state().get("scheduler_task_states")
    assert isinstance(scheduler_states, dict)
    assert scheduler_states["telemetry"]["status"] == "running"
    assert scheduler_states["telemetry"]["last_started_at"] is not None
    assert scheduler_states["operational_mqtt_health"]["status"] == "running"
    assert scheduler_states["gmail_status_polling"]["status"] in {"idle", "inactive"}
    assert scheduler_states["gmail_fetch_last_hour"]["status"] in {"idle", "inactive"}
    assert scheduler_states["shipment_live_tracking_refresh"]["status"] in {"idle", "inactive"}

    await service.stop()


@pytest.mark.asyncio
async def test_scheduler_shutdown_marks_long_lived_tasks_stopped(config, core_client_factory):
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())

    await service.start()
    service.state.trust_state = "trusted"
    service.state.operational_readiness = True
    service.background_tasks.sync_runtime_task_gating()

    await service.stop()

    scheduler_states = service.runtime.runtime_task_state()["scheduler_task_states"]
    assert scheduler_states["telemetry"]["status"] == "stopped"
    assert scheduler_states["operational_mqtt_health"]["status"] == "stopped"
    assert scheduler_states["gmail_status_polling"]["status"] == "stopped"
    assert scheduler_states["gmail_fetch_last_hour"]["status"] == "stopped"
    assert scheduler_states["shipment_live_tracking_refresh"]["status"] == "stopped"


def test_public_scheduled_task_status_normalization():
    assert BackgroundTaskManager.scheduled_task_public_status("active") == "scheduled"
    assert BackgroundTaskManager.scheduled_task_public_status("inactive") == "idle"
    assert BackgroundTaskManager.scheduled_task_public_status("pending") == "idle"
    assert BackgroundTaskManager.scheduled_task_public_status("degraded") == "failing"
    assert BackgroundTaskManager.scheduled_task_public_status("running") == "running"
    assert BackgroundTaskManager.scheduled_task_public_status("healthy") == "healthy"


@pytest.mark.asyncio
async def test_scheduler_runs_due_shipment_live_tracking_refresh(config, core_client_factory, monkeypatch):
    config.track123_enabled = True
    config.track123_api_secret = "secret-test"
    service = NodeService(config, core_client=core_client_factory(build_core_app()), mqtt_manager=FakeMQTTManager())
    await service.start()
    service.state.trust_state = "trusted"
    service.state.operational_readiness = True
    calls = []

    async def fake_refresh_all_shipment_live_tracking():
        calls.append("refresh")
        return {"status": "ok", "refreshed": 2, "failed": 0, "total": 2, "results": []}

    monkeypatch.setattr(service, "refresh_all_shipment_live_tracking", fake_refresh_all_shipment_live_tracking)
    now = service.state.created_at.replace(minute=10, second=0, microsecond=0)

    result = await service.background_tasks.run_due_shipment_live_tracking_refresh(now)

    await service.stop()

    assert result == {"status": "ok", "refreshed": 2, "failed": 0, "total": 2, "results": []}
    assert calls == ["refresh"]
    state = service.runtime.runtime_task_state()["scheduler_task_states"]["shipment_live_tracking_refresh"]
    assert state["status"] == "stopped"
    assert state["last_slot_key"] == now.astimezone().isoformat()
