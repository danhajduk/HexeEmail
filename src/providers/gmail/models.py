from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
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

    @model_validator(mode="after")
    def ensure_modify_scope(self) -> GmailOAuthConfig:
        scopes = list(self.requested_scopes.scopes)
        modify_scope = "https://www.googleapis.com/auth/gmail.modify"
        if modify_scope not in scopes:
            scopes.append(modify_scope)
            self.requested_scopes = GmailRequestedScopes(scopes=scopes)
        return self


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
    local_label: str | None = None
    local_label_confidence: float | None = None
    manual_classification: bool = False


class GmailTrainingLabel(str, Enum):
    ACTION_REQUIRED = "action_required"
    DIRECT_HUMAN = "direct_human"
    FINANCIAL = "financial"
    ORDER = "order"
    INVOICE = "invoice"
    SHIPMENT = "shipment"
    SECURITY = "security"
    SYSTEM = "system"
    NEWSLETTER = "newsletter"
    MARKETING = "marketing"
    UNKNOWN = "unknown"


class GmailTrainingRecipientFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_me_only: bool = False
    cc_me: bool = False
    recipient_count: str = "rc_1"


class GmailTrainingFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_attachment: bool = False
    is_reply: bool = False
    is_forward: bool = False
    has_unsubscribe: bool = False


class GmailFlattenedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    message_id: str
    sender_email: str | None = None
    sender_domain: str | None = None
    recipient: str | None = None
    recipient_flags: GmailTrainingRecipientFlags = Field(default_factory=GmailTrainingRecipientFlags)
    subject: str | None = None
    flags: GmailTrainingFlags = Field(default_factory=GmailTrainingFlags)
    body_preview: str | None = None
    gmail_labels: list[str] = Field(default_factory=list)
    local_label: str | None = None
    local_label_confidence: float | None = None
    manual_classification: bool = False


class GmailManualClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    label: GmailTrainingLabel
    confidence: float = 1.0

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class GmailManualClassificationBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GmailManualClassificationInput] = Field(default_factory=list)


class GmailSemiAutoClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    selected_label: GmailTrainingLabel
    predicted_label: GmailTrainingLabel
    predicted_confidence: float

    @field_validator("predicted_confidence")
    @classmethod
    def validate_predicted_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("predicted_confidence must be between 0 and 1")
        return value


class GmailSemiAutoClassificationBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GmailSemiAutoClassificationInput] = Field(default_factory=list)


class GmailSpamhausCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    message_id: str
    sender_email: str | None = None
    sender_domain: str | None = None
    checked: bool = False
    listed: bool = False
    status: Literal["pending", "clean", "listed", "error", "invalid_sender"] = "pending"
    checked_at: datetime | None = None
    detail: str | None = None


class GmailSpamhausSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    checked_count: int = 0
    pending_count: int = 0
    listed_count: int = 0
    error_count: int = 0
    latest_checked_at: datetime | None = None


class GmailQuotaUsageSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    limit_per_minute: int = 15000
    used_last_minute: int = 0
    remaining_last_minute: int = 15000
    recent_operations: dict[str, int] = Field(default_factory=dict)
    last_request_at: datetime | None = None


class GmailTrainingDatasetRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    message_id: str
    normalized_text: str
    label: GmailTrainingLabel
    label_source: Literal["manual", "local_auto", "gmail_bootstrap", "rule_bootstrap"]
    sample_weight: float
    normalization_version: str
    received_at: datetime


class GmailTrainingDatasetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_rows_scanned: int = 0
    excluded_mailbox_count: int = 0
    excluded_no_label_count: int = 0
    included_count: int = 0
    included_by_label_source: dict[str, int] = Field(default_factory=dict)
    per_label_counts: dict[str, int] = Field(default_factory=dict)
    weighted_counts: dict[str, float] = Field(default_factory=dict)
    excluded_mailbox_labels: list[str] = Field(default_factory=list)
    gmail_mapping_config: dict[str, str] = Field(default_factory=dict)
    bootstrap_threshold: float = 0.0


class GmailFetchWindowState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_run_at: datetime | None = None
    last_run_reason: Literal["manual", "scheduled", "auto"] | None = None
    last_slot_key: str | None = None


class GmailFetchScheduleState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yesterday: GmailFetchWindowState = Field(default_factory=GmailFetchWindowState)
    today: GmailFetchWindowState = Field(default_factory=GmailFetchWindowState)
    last_hour: GmailFetchWindowState = Field(default_factory=GmailFetchWindowState)
