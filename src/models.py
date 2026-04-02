from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OnboardingStatus = Literal["not_started", "pending", "approved", "rejected", "expired", "consumed", "invalid"]
TrustState = Literal["untrusted", "pending", "trusted", "rejected", "expired", "consumed", "invalid"]


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


class StatusResponse(BaseModel):
    node_name: str
    node_type: str
    node_software_version: str
    trust_state: TrustState
    node_id: str | None
    mqtt_connection_status: str
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
