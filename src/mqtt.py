from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import paho.mqtt.client as mqtt

from logging_utils import get_logger
from models import TrustMaterial


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
    def __init__(self, heartbeat_seconds: float = 30.0, on_heartbeat: Callable[[], None] | None = None) -> None:
        self.heartbeat_seconds = heartbeat_seconds
        self.on_heartbeat = on_heartbeat
        self.status = MqttStatus()
        self._client: mqtt.Client | None = None
        self._trust: TrustMaterial | None = None
        self._presence_topic: str | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def connect(self, trust_material: TrustMaterial) -> None:
        self._trust = trust_material
        self._presence_topic = f"hexe/nodes/{trust_material.node_id}/presence"
        self._client = _build_client(trust_material.operational_mqtt_identity)
        self._client.username_pw_set(
            trust_material.operational_mqtt_identity,
            trust_material.operational_mqtt_token,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
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
        self._publish_presence("online")
        self._start_heartbeat_loop()

    def _on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties=None) -> None:
        if self.status.state != "disconnected":
            self.status.state = "reconnecting"
            LOGGER.warning("MQTT disconnected", extra={"event_data": {"state": "disconnected", "reason_code": str(reason_code)}})

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
