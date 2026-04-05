from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import paho.mqtt.client as mqtt

from logging_utils import get_logger
from node_models.node import TrustMaterial
from node_models.notifications import NodeNotificationRequest, NodeNotificationResult


LOGGER = get_logger(__name__)


def _build_client(client_id: str) -> mqtt.Client:
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id=client_id)


@dataclass
class MqttStatus:
    state: str = "disconnected"


class MQTTManager:
    def __init__(
        self,
        heartbeat_seconds: float = 30.0,
        on_heartbeat: Callable[[], None] | None = None,
        on_notification_result: Callable[[NodeNotificationResult], None] | None = None,
        on_connected: Callable[[], None] | None = None,
    ) -> None:
        self.heartbeat_seconds = heartbeat_seconds
        self.on_heartbeat = on_heartbeat
        self.on_notification_result = on_notification_result
        self.on_connected = on_connected
        self.status = MqttStatus()
        self._client: mqtt.Client | None = None
        self._trust: TrustMaterial | None = None
        self._presence_topic: str | None = None
        self._notification_request_topic: str | None = None
        self._notification_result_topic: str | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def connect(self, trust_material: TrustMaterial) -> None:
        self._trust = trust_material
        self._presence_topic = f"hexe/nodes/{trust_material.node_id}/presence"
        self._notification_request_topic = f"hexe/nodes/{trust_material.node_id}/notify/request"
        self._notification_result_topic = f"hexe/nodes/{trust_material.node_id}/notify/result"
        self._client = _build_client(trust_material.operational_mqtt_identity)
        self._client.username_pw_set(
            trust_material.operational_mqtt_identity,
            trust_material.operational_mqtt_token,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self.status.state = "connecting"
        self._client.connect_async(
            trust_material.operational_mqtt_host,
            trust_material.operational_mqtt_port,
            keepalive=max(int(self.heartbeat_seconds * 2), 30),
        )
        self._client.loop_start()

    def disconnect(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2)
        if self._client is not None:
            self._publish_presence("offline")
            self._client.disconnect()
            self._client.loop_stop()
        self.status.state = "disconnected"

    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties=None) -> None:
        self.status.state = "connected"
        LOGGER.info("MQTT connected", extra={"event_data": {"state": "connected"}})
        if self._notification_result_topic:
            client.subscribe(self._notification_result_topic, qos=1)
        self._publish_presence("online")
        if self.on_connected is not None:
            self.on_connected()
        self._start_heartbeat_loop()

    def _on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties=None) -> None:
        if self.status.state != "disconnected":
            self.status.state = "reconnecting"
            LOGGER.warning("MQTT disconnected", extra={"event_data": {"state": "disconnected", "reason_code": str(reason_code)}})

    def _on_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
        if message.topic != self._notification_result_topic:
            return
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            result = NodeNotificationResult.model_validate(payload)
        except Exception as exc:
            LOGGER.warning(
                "MQTT notification result was invalid",
                extra={"event_data": {"topic": message.topic, "detail": str(exc)}},
            )
            return
        LOGGER.info(
            "MQTT notification result received",
            extra={
                "event_data": {
                    "request_id": result.request_id,
                    "status": result.status,
                    "accepted": result.accepted,
                    "error": result.error,
                }
            },
        )
        if self.on_notification_result is not None:
            self.on_notification_result(result)

    def _start_heartbeat_loop(self) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self.heartbeat_seconds):
            self._publish_presence("heartbeat")
            if self.on_heartbeat is not None:
                self.on_heartbeat()

    def _publish_presence(self, event_type: str) -> None:
        if self._client is None or self._presence_topic is None or self._trust is None:
            return
        payload = {
            "event": event_type,
            "node_id": self._trust.node_id,
            "node_type": self._trust.node_type,
            "ts": datetime.now(UTC).isoformat(),
        }
        self._client.publish(self._presence_topic, json.dumps(payload), qos=1, retain=(event_type != "heartbeat"))

    def publish_notification_request(self, request: NodeNotificationRequest) -> bool:
        if self._client is None or self._notification_request_topic is None:
            return False
        self._client.publish(
            self._notification_request_topic,
            request.model_dump_json(exclude_none=True),
            qos=1,
            retain=False,
        )
        LOGGER.info(
            "MQTT notification request published",
            extra={
                "event_data": {
                    "request_id": request.request_id,
                    "kind": request.kind,
                    "severity": request.delivery.severity if request.delivery is not None else None,
                    "topic": self._notification_request_topic,
                }
            },
        )
        return True
