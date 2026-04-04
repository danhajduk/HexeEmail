from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


OnboardingStatus = Literal["not_started", "pending", "approved", "rejected", "expired", "consumed", "invalid"]
TrustState = Literal["untrusted", "pending", "trusted", "rejected", "expired", "consumed", "invalid"]
NotificationKind = Literal["popup", "event", "state"]
NotificationSeverity = Literal["info", "success", "warning", "error", "critical"]
NotificationPriority = Literal["low", "normal", "high", "urgent"]
NotificationUrgency = Literal["info", "error", "notification", "urgent", "actions_needed"]
NotificationResultStatus = Literal["accepted", "rejected"]


class OperatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_base_url: str | None = None
    node_name: str | None = None
    selected_task_capabilities: list[str] = Field(default_factory=list)


class OperatorConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_base_url: str | None = None
    node_name: str | None = None
    selected_task_capabilities: list[str] = Field(default_factory=list)


class TaskCapabilitySelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_task_capabilities: list[str] = Field(default_factory=list)


class TaskRoutingRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_family: str
    requested_node_type: str | None = None
    requested_provider: str | None = None
    inputs: dict[str, object] = Field(default_factory=dict)
    constraints: dict[str, object] = Field(default_factory=dict)


class TaskRoutingPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_family: str
    requested_node_type: str | None = None
    requested_provider: str | None = None
    local_node_type: str
    local_selected_task_capabilities: list[str] = Field(default_factory=list)
    local_node_can_execute: bool = False
    should_delegate_to_core: bool = False
    capability_declared: bool = False
    detail: str


class CoreServiceResolveRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_family: str
    type: str | None = "ai"
    task_context: dict[str, object] = Field(default_factory=dict)
    preferred_provider: str | None = None


class CoreServiceAuthorizeRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_family: str
    type: str | None = "ai"
    task_context: dict[str, object] = Field(default_factory=dict)
    service_id: str
    provider: str
    model_id: str | None = None


class RuntimeDirectExecutionRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_family: str
    target_api_base_url: str | None = None
    service_token: str | None = None
    grant_id: str | None = None
    service_id: str | None = None
    provider: str | None = None
    model_id: str | None = None
    content_type: str = "email"
    subject: str | None = None
    body: str | None = None


class RuntimePromptExecutionRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_api_base_url: str | None = None
    subject: str | None = None
    body: str | None = None


class RuntimePromptSyncRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_api_base_url: str | None = None


class RefreshTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force_refresh: bool = False


class ServiceRestartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str


class RuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_session_id: str | None = None
    approval_url: str | None = None
    onboarding_status: OnboardingStatus = "not_started"
    onboarding_expires_at: datetime | None = None
    node_id: str | None = None
    paired_core_id: str | None = None
    trust_state: TrustState = "untrusted"
    trust_token_present: bool = False
    mqtt_credentials_present: bool = False
    operational_mqtt_host: str | None = None
    operational_mqtt_port: int | None = None
    last_finalize_status: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    trusted_at: datetime | None = None
    last_poll_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_error: str | None = None
    capability_declaration_status: str | None = None
    capability_declared_at: datetime | None = None
    enabled_providers: list[str] = Field(default_factory=list)
    governance_sync_status: str | None = None
    governance_synced_at: datetime | None = None
    active_governance_version: str | None = None
    operational_readiness: bool = False
    runtime_email_classify_counter: int = 0
    runtime_prompt_sync_target_api_base_url: str | None = None
    runtime_prompt_sync_weekly_slot_key: str | None = None
    runtime_prompt_sync_last_scheduled_at: datetime | None = None
    runtime_monthly_authorize_slot_key: str | None = None
    runtime_monthly_authorize_last_run_at: datetime | None = None
    gmail_hourly_batch_classification_slot_key: str | None = None
    gmail_hourly_batch_classification_last_run_at: datetime | None = None
    gmail_last_hour_pipeline_state: dict[str, object] = Field(default_factory=dict)
    gmail_fetch_scheduler_state: dict[str, object] = Field(default_factory=dict)
    runtime_task_state: dict[str, object] = Field(default_factory=dict)


class TrustMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_type: str
    paired_core_id: str
    node_trust_token: str
    operational_mqtt_identity: str
    operational_mqtt_token: str
    operational_mqtt_host: str
    operational_mqtt_port: int
    issued_at: str | None = None
    source_session_id: str | None = None
    trust_status: str = "trusted"


class ReadinessStatus(BaseModel):
    live: bool = True
    ready: bool
    version: str
    startup_error: str | None = None


class OnboardingStatusResponse(BaseModel):
    node_name: str
    node_type: str
    node_software_version: str
    session_id: str | None
    approval_url: str | None
    onboarding_status: OnboardingStatus
    trust_state: TrustState
    node_id: str | None
    expires_at: datetime | None
    last_error: str | None
    required_inputs: list[str] = Field(default_factory=list)


class MqttHealthResponse(BaseModel):
    health_status: str | None = None
    status_freshness_state: str = "unknown"
    status_stale: bool = False
    status_inactive: bool = False
    status_age_s: int | None = None
    status_stale_after_s: int
    status_inactive_after_s: int
    last_status_report_at: datetime | None = None


class StatusResponse(BaseModel):
    node_name: str
    node_type: str
    node_software_version: str
    trust_state: TrustState
    node_id: str | None
    paired_core_id: str | None = None
    mqtt_connection_status: str
    mqtt_health: MqttHealthResponse
    operational_mqtt_host: str | None = None
    operational_mqtt_port: int | None = None
    onboarding_status: OnboardingStatus
    providers: list[str]
    required_inputs: list[str] = Field(default_factory=list)
    supported_providers: list[str] = Field(default_factory=list)
    enabled_providers: list[str] = Field(default_factory=list)
    provider_account_summaries: dict[str, object] = Field(default_factory=dict)
    governance_sync_status: str | None = None
    capability_declaration_status: str | None = None
    active_governance_version: str | None = None
    last_heartbeat_at: datetime | None = None
    trusted_at: datetime | None = None
    operational_readiness: bool = False
    capability_setup: dict[str, object] = Field(default_factory=dict)


class OperatorConfigResponse(BaseModel):
    core_base_url: str
    node_name: str
    selected_task_capabilities: list[str] = Field(default_factory=list)
    node_type: str
    node_software_version: str
    api_port: int
    ui_port: int


class UiBootstrapResponse(BaseModel):
    config: OperatorConfigResponse
    onboarding: OnboardingStatusResponse
    status: StatusResponse
    required_inputs: list[str]
    can_start_onboarding: bool
    runtime_task_state: dict[str, object] = Field(default_factory=dict)
    scheduled_tasks: list[dict[str, object]] = Field(default_factory=list)
    scheduled_task_legend: list[dict[str, object]] = Field(default_factory=list)


class GmailConnectStartResponse(BaseModel):
    provider_id: str
    account_id: str
    connect_url: str
    expires_at: datetime


class GmailOAuthCallbackResponse(BaseModel):
    provider_id: str
    account_id: str
    status: str
    granted_scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


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
