from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GmailRequestedScopes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scopes: list[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ]
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        normalized = [scope.strip() for scope in value if scope.strip()]
        if not normalized:
            raise ValueError("at least one Gmail scope is required")
        return normalized


class GmailOAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oauth_client_type: Literal["web"] = "web"
    enabled: bool = False
    client_id: str | None = None
    client_secret_ref: str | None = None
    redirect_uri: str | None = None
    requested_scopes: GmailRequestedScopes = Field(default_factory=GmailRequestedScopes)

    @field_validator("oauth_client_type", mode="before")
    @classmethod
    def normalize_client_type(cls, value: str | None) -> str:
        if value in {None, "", "web", "desktop"}:
            return "web"
        raise ValueError("oauth_client_type must be web")


class GmailAccountConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    display_name: str | None = None
    enabled: bool = True


class GmailTokenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    granted_scopes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GmailOAuthSessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    account_id: str
    client_id: str | None = None
    redirect_uri: str
    code_verifier: str
    correlation_id: str | None = None
    core_id: str | None = None
    node_id: str | None = None
    flow_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=10))
    consumed_at: datetime | None = None
    authorization_url: str | None = None
    public_state: str | None = None


class GmailMailboxStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    email_address: str | None = None
    status: Literal["pending", "ok", "error"] = "pending"
    unread_inbox_count: int = 0
    unread_today_count: int = 0
    unread_yesterday_count: int = 0
    unread_last_hour_count: int = 0
    checked_at: datetime | None = None
    detail: str | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_unread_week_count(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if "unread_last_hour_count" not in payload and "unread_week_count" in payload:
            payload["unread_last_hour_count"] = payload["unread_week_count"]
        payload.pop("unread_week_count", None)
        return payload


class GmailStoredMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    message_id: str
    thread_id: str | None = None
    subject: str | None = None
    sender: str | None = None
    recipients: list[str] = Field(default_factory=list)
    snippet: str | None = None
    label_ids: list[str] = Field(default_factory=list)
    received_at: datetime
    raw_payload: str | None = None


class GmailFetchWindowState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_run_at: datetime | None = None
    last_run_reason: Literal["manual", "scheduled"] | None = None
    last_slot_key: str | None = None


class GmailFetchScheduleState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yesterday: GmailFetchWindowState = Field(default_factory=GmailFetchWindowState)
    today: GmailFetchWindowState = Field(default_factory=GmailFetchWindowState)
    last_hour: GmailFetchWindowState = Field(default_factory=GmailFetchWindowState)
