from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from node_models.common import OnboardingStatus, TrustState


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
    message_id: str | None = None
    subject: str | None = None
    body: str | None = None


class RuntimePromptSyncRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_api_base_url: str | None = None
    review_due_migration: bool = False


class RuntimePromptReviewRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_api_base_url: str | None = None
    prompt_id: str
    review_status: str = "approved"
    reason: str | None = None


class RuntimeTaskSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_calls_enabled: bool | None = None
    provider_calls_enabled: bool | None = None


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
    runtime_prompt_review_due_migration_last_run_at: datetime | None = None
    runtime_prompt_review_due_migration_target_api_base_url: str | None = None
    runtime_prompt_review_due_migration_result: dict[str, object] = Field(default_factory=dict)
    runtime_monthly_authorize_slot_key: str | None = None
    runtime_monthly_authorize_last_run_at: datetime | None = None
    gmail_hourly_batch_classification_slot_key: str | None = None
    gmail_hourly_batch_classification_last_run_at: datetime | None = None
    gmail_last_hour_pipeline_state: dict[str, object] = Field(default_factory=dict)
    gmail_fetch_scheduler_state: dict[str, object] = Field(default_factory=dict)
    runtime_task_state: dict[str, object] = Field(default_factory=dict)
