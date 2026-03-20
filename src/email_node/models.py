from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OnboardingStatus = Literal["not_started", "pending", "approved", "rejected", "expired", "consumed", "invalid"]
TrustState = Literal["untrusted", "pending", "trusted", "rejected", "expired", "consumed", "invalid"]


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


class StatusResponse(BaseModel):
    node_name: str
    node_type: str
    node_software_version: str
    trust_state: TrustState
    node_id: str | None
    mqtt_connection_status: str
    onboarding_status: OnboardingStatus
    providers: list[str]
