from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from node_models.common import (
    NotificationKind,
    NotificationPriority,
    NotificationResultStatus,
    NotificationSeverity,
    NotificationUrgency,
)


class NotificationTargets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    broadcast: bool = False
    users: list[str] = Field(default_factory=list)
    hosts: list[str] = Field(default_factory=list)
    sessions: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)


class NotificationDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: NotificationSeverity = "info"
    priority: NotificationPriority = "normal"
    urgency: NotificationUrgency | None = None
    channels: list[str] = Field(default_factory=list)
    ttl_seconds: int | None = None
    dedupe_key: str | None = None


class NotificationContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    subtitle: str | None = None
    message: str | None = None
    body: str | None = None


class NotificationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str | None = None
    action: str | None = None
    summary: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class NotificationStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    reason: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class NotificationSourceHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str | None = None
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeNotificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    request_id: str
    created_at: datetime
    node_id: str | None = None
    kind: NotificationKind
    targets: NotificationTargets
    delivery: NotificationDelivery | None = None
    retain: bool = False
    source: NotificationSourceHint | None = None
    content: NotificationContent | None = None
    event: NotificationEvent | None = None
    state: NotificationStatePayload | None = None
    data: dict[str, Any] | None = None


class NodeNotificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    request_id: str
    node_id: str
    status: NotificationResultStatus
    accepted: bool
    created_at: datetime
    notification_id: str | None = None
    internal_topic: str | None = None
    error: str | None = None
    requested_external_targets: list[str] = Field(default_factory=list)
