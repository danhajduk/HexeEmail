from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from logging_utils import get_logger
from node_models.notifications import (
    NodeNotificationRequest,
    NodeNotificationResult,
    NotificationContent,
    NotificationDelivery,
    NotificationEvent,
    NotificationSourceHint,
    NotificationTargets,
)


LOGGER = get_logger(__name__)


class NotificationManager:
    def __init__(self, service: Any) -> None:
        self.service = service
        self.gmail_fetch_notification_state: str | None = None
        self.mqtt_connect_notification_count = 0

    def connect_mqtt_if_possible(self) -> None:
        if self.service.trust_material is None:
            return
        self.service.mqtt_manager.connect(self.service.trust_material)

    def record_heartbeat(self) -> None:
        self.service.state.last_heartbeat_at = datetime.now(UTC).replace(tzinfo=None)
        self.service.state_store.save(self.service.state)

    def handle_notification_result(self, result: NodeNotificationResult) -> None:
        if result.accepted:
            return
        LOGGER.warning(
            "Core rejected user notification request",
            extra={
                "event_data": {
                    "request_id": result.request_id,
                    "node_id": result.node_id,
                    "error": result.error,
                }
            },
        )

    def handle_mqtt_connected(self) -> None:
        self.mqtt_connect_notification_count += 1
        generation = self.mqtt_connect_notification_count
        label = "Hexe Email online" if generation == 1 else "Hexe Email back online"
        message = (
            "The email node finished startup and is connected to Core."
            if generation == 1
            else "The email node reconnected to Core and is back online."
        )
        self.send_user_notification(
            title=label,
            message=message,
            severity="success",
            urgency="notification",
            dedupe_key=f"node-online-{generation}",
            event_type="node_online" if generation == 1 else "node_reconnected",
            summary="Email node connected to Core",
            source_component="mqtt_runtime",
            data={"connection_generation": generation, "connection_state": "connected"},
        )

    def send_user_notification(
        self,
        *,
        title: str,
        message: str,
        severity: str,
        urgency: str,
        dedupe_key: str,
        event_type: str,
        summary: str,
        source_component: str,
        data: dict[str, object] | None = None,
    ) -> bool:
        if self.service.state.trust_state != "trusted" or not self.service.state.node_id:
            return False
        if self.service.mqtt_manager.status.state != "connected":
            LOGGER.info(
                "Skipping user notification because MQTT is not connected",
                extra={
                    "event_data": {
                        "dedupe_key": dedupe_key,
                        "connection_state": self.service.mqtt_manager.status.state,
                    }
                },
            )
            return False

        request = NodeNotificationRequest(
            request_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC),
            node_id=self.service.state.node_id,
            kind="event",
            targets=NotificationTargets(broadcast=True, external=["ha"]),
            delivery=NotificationDelivery(
                severity=severity,
                priority="high" if severity in {"warning", "error", "critical"} else "normal",
                urgency=urgency,
                dedupe_key=dedupe_key,
                channels=["event", "external"],
                ttl_seconds=3600,
            ),
            source=NotificationSourceHint(
                component=source_component,
                label=self.service.effective_node_name() or self.service.config.node_type,
                metadata={"node_type": self.service.config.node_type},
            ),
            content=NotificationContent(title=title, message=message),
            event=NotificationEvent(
                event_type=event_type,
                summary=summary,
                attributes={"component": source_component},
            ),
            data=data or {},
        )
        return self.service.mqtt_manager.publish_notification_request(request)

    def set_gmail_fetch_notification_state(self, next_state: str, detail: str) -> None:
        previous = self.gmail_fetch_notification_state
        self.gmail_fetch_notification_state = next_state
        if next_state == previous:
            return
        if next_state == "warning":
            self.send_user_notification(
                title="Hexe Email warning",
                message=detail,
                severity="warning",
                urgency="actions_needed",
                dedupe_key="gmail-fetch-warning",
                event_type="gmail_fetch_warning",
                summary="Gmail fetch scheduler needs attention",
                source_component="gmail_fetch_scheduler",
                data={"status": "warning"},
            )
            return
        if next_state == "error":
            self.send_user_notification(
                title="Hexe Email error",
                message=detail,
                severity="error",
                urgency="urgent",
                dedupe_key="gmail-fetch-error",
                event_type="gmail_fetch_error",
                summary="Gmail fetch scheduler hit an error",
                source_component="gmail_fetch_scheduler",
                data={"status": "error"},
            )
            return
        if next_state == "healthy" and previous in {"warning", "error"}:
            self.send_user_notification(
                title="Hexe Email back online",
                message="Gmail fetch scheduling recovered and is running again.",
                severity="success",
                urgency="notification",
                dedupe_key="gmail-fetch-recovered",
                event_type="gmail_fetch_recovered",
                summary="Gmail fetch scheduler recovered",
                source_component="gmail_fetch_scheduler",
                data={"status": "healthy", "recovered_from": previous},
            )
