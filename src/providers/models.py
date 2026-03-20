from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProviderId(StrEnum):
    GMAIL = "gmail"
    SMTP = "smtp"
    IMAP = "imap"
    GRAPH = "graph"


ProviderState = Literal["not_configured", "disabled", "oauth_pending", "configured", "connected", "degraded", "revoked"]
ProviderAccountStatus = Literal[
    "not_configured",
    "oauth_pending",
    "token_exchanged",
    "connected",
    "degraded",
    "revoked",
]
ProviderHealthState = Literal["unknown", "connected", "degraded", "revoked", "invalid_config", "oauth_pending"]


class ProviderValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    missing_fields: list[str] = Field(default_factory=list)
    invalid_fields: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    status: ProviderHealthState
    detail: str | None = None
    checked_at: datetime | None = None
    account_id: str | None = None


class ProviderAccountRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    account_id: str
    status: ProviderAccountStatus = "not_configured"
    email_address: str | None = None
    display_name: str | None = None
    external_account_id: str | None = None
    last_error: str | None = None
    last_connected_at: datetime | None = None
    updated_at: datetime | None = None


class ProviderActivationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    provider_state: ProviderState = "not_configured"
    enabled: bool = False
    configured: bool = False
    supported: bool = False
    account_count: int = 0
    connected_account_count: int = 0
    health: ProviderHealth | None = None
    accounts: list[ProviderAccountRecord] = Field(default_factory=list)


class EmailProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    enabled: bool = False


class EmailProviderHealth(ProviderHealth):
    pass


class OutboundSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    recipient: str
    subject: str
    text_body: str


class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    supports_send: bool = False
    supports_receive: bool = False
    supports_oauth: bool = False
