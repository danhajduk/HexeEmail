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
    action_decision_payload: dict[str, object] | None = None
    action_decision_prompt_version: str | None = None
    action_decision_updated_at: datetime | None = None
    action_decision_raw_response: dict[str, object] | None = None
    action_decision_raw_response_updated_at: datetime | None = None


class GmailPhase1FetchedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mime_type: Literal["text/plain", "text/html"]
    content: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    content_transfer_encoding: str | None = None
    charset: str | None = None
    mime_boundary: str | None = None


class GmailPhase1FetchedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase1.fetch.v1"
    provider: str = "gmail"
    account_id: str
    message_id: str
    thread_id: str | None = None
    message_id_header: str | None = None
    subject: str | None = None
    sender: str | None = None
    date: str | None = None
    received_at: datetime | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    text_body: GmailPhase1FetchedBody | None = None
    html_body: GmailPhase1FetchedBody | None = None
    fetch_status: Literal["success", "partial", "failed"] = "success"
    fetch_error: str | None = None
    fetch_diagnostics: list[str] = Field(default_factory=list)
    mime_parse_status: Literal["success", "partial", "failed"] = "success"
    mime_diagnostics: list[str] = Field(default_factory=list)
    mime_boundaries: list[str] = Field(default_factory=list)
    part_inventory: list[dict[str, object]] = Field(default_factory=list)


class GmailPhase1SenderIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_sender: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None


class GmailPhase1BodyAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    html_available: bool = False
    text_available: bool = False
    html_length: int = 0
    text_length: int = 0


class GmailPhase1DecodeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "partial", "failed"] = "success"
    diagnostics: list[str] = Field(default_factory=list)


class GmailPhase1DiagnosticItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    detail: str


class GmailPhase1NormalizationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalizer_version: str
    decode_strategy: str
    mime_parse_status: Literal["success", "partial", "failed"]
    body_selection_strategy: str
    normalized_at: datetime


class GmailPhase1Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    provider: str
    message_id: str
    thread_id: str | None = None
    provider_message_id: str
    provider_thread_id: str | None = None
    rfc_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None
    received_at: datetime | None = None
    selected_body_type: Literal["html", "text", "none"] = "none"
    selected_body_source: str | None = None
    selected_body_selection_path: str | None = None
    handoff_ready: bool = False
    fetch_status: Literal["success", "partial", "failed"] = "success"
    mime_parse_status: Literal["success", "partial", "failed"] = "success"
    validation_status: Literal["success", "partial", "failed"] = "failed"


class GmailPhase2Link(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    url: str
    raw_url: str | None = None
    normalized_url: str | None = None
    link_type: Literal["order_action", "tracking_action", "document_action", "account", "other"] = "other"
    source: Literal["html_anchor", "plain_text", "derived"] = "derived"
    is_tracking: bool = False
    is_valid: bool = True
    diagnostics: list[str] = Field(default_factory=list)


class GmailPhase2Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_char_count: int = 0
    output_char_count: int = 0
    reduction_ratio: float = 0.0
    input_line_count: int = 0
    output_line_count: int = 0
    lines_removed: int = 0
    links_extracted: int = 0
    cutoff_rules_triggered: int = 0
    applied_rule_count: int = 0


class GmailPhase2NormalizationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scrubber_version: str
    source_strategy: str
    body_input_type: Literal["html", "text", "none"]
    normalized_at: datetime


class GmailPhase1NormalizedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase1.normalized.v1"
    provider: str = "gmail"
    message_id: str = Field(description="Canonical Gmail provider message identifier used by downstream phases.")
    thread_id: str | None = Field(
        default=None,
        description="Canonical Gmail provider thread identifier for thread-scoped operations.",
    )
    provider_message_id: str = Field(description="Raw Gmail provider message id, distinct from RFC Message-ID headers.")
    provider_thread_id: str | None = Field(
        default=None,
        description="Raw Gmail provider thread id, distinct from the RFC Message-ID header.",
    )
    rfc_message_id: str | None = Field(
        default=None,
        description="RFC822 Message-ID header preserved separately from provider ids.",
    )
    subject: str | None = Field(default=None, description="Canonical normalized subject derived from Gmail headers.")
    sender_name: str | None = Field(default=None, description="Canonical normalized sender display name.")
    sender_email: str | None = Field(default=None, description="Canonical normalized sender email address.")
    sender_domain: str | None = Field(default=None, description="Canonical normalized sender domain.")
    raw_sender: str | None = None
    received_at: datetime | None = Field(default=None, description="Canonical received timestamp from Gmail metadata.")
    raw_html: str | None = None
    raw_text: str | None = None
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Preserved raw headers for reference; top-level normalized fields are authoritative.",
    )
    fetch_status: Literal["success", "partial", "failed"] = "success"
    fetch_error: str | None = None
    fetch_diagnostics: list[str] = Field(default_factory=list)
    mime_parse_status: Literal["success", "partial", "failed"] = "success"
    mime_diagnostics: list[str] = Field(default_factory=list)
    sender_normalization_status: Literal["success", "partial", "failed"] = "failed"
    sender_diagnostics: list[str] = Field(default_factory=list)
    content_transfer_encoding: str | None = None
    mime_boundaries: list[str] = Field(default_factory=list)
    mime_parts: list[dict[str, object]] = Field(default_factory=list)
    part_inventory: list[dict[str, object]] = Field(
        default_factory=list,
        description="Legacy alias for MIME part inventory; `mime_parts` is the authoritative Phase 1 handoff field.",
    )
    body_availability: GmailPhase1BodyAvailability = Field(default_factory=GmailPhase1BodyAvailability)
    decoded_html: str | None = None
    decoded_text: str | None = None
    decoded_html_quality: Literal["rich_html", "usable_html", "usable_text", "fallback_text", "empty", "corrupted"] = "empty"
    decoded_text_quality: Literal["rich_html", "usable_html", "usable_text", "fallback_text", "empty", "corrupted"] = "empty"
    decode_state: GmailPhase1DecodeState = Field(default_factory=GmailPhase1DecodeState)
    selected_body_type: Literal["html", "text", "none"] = "none"
    selected_body_content: str | None = None
    selected_body_quality: Literal["rich_html", "usable_html", "usable_text", "fallback_text", "empty", "corrupted"] = "empty"
    body_selection_status: Literal["success", "partial", "failed"] = "failed"
    body_selection_reason: str | None = None
    selected_body_reason: str | None = None
    selected_body_source: str | None = None
    selected_body_selection_path: str | None = None
    raw_html_hash: str | None = None
    raw_text_hash: str | None = None
    decoded_html_hash: str | None = None
    decoded_text_hash: str | None = None
    selected_body_hash: str | None = None
    handoff_ready: bool = False
    validation_status: Literal["success", "partial", "failed"] = "failed"
    validation_diagnostics: list[str] = Field(default_factory=list)
    stage_diagnostics: dict[str, list[GmailPhase1DiagnosticItem]] = Field(default_factory=dict)
    normalization_metadata: GmailPhase1NormalizationMetadata | None = None


class GmailPhase2WorkingEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase2.working.v1"
    phase1_reference: GmailPhase1Reference
    message_id: str
    thread_id: str | None = None
    provider_message_id: str
    provider_thread_id: str | None = None
    rfc_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None
    selected_body_type: Literal["html", "text", "none"] = "none"
    selected_body_source: str | None = None
    selected_body_selection_path: str | None = None
    selected_body_content: str | None = None
    source_text: str | None = None
    visible_text: str | None = None
    normalized_text: str | None = None
    transactional_candidates: list[str] = Field(default_factory=list)
    selected_transactional_text: str | None = None
    normalized_lines: list[str] = Field(default_factory=list)
    extracted_links: list[GmailPhase2Link] = Field(default_factory=list)
    applied_rules: list[str] = Field(default_factory=list)
    stage_statuses: dict[str, Literal["success", "partial", "failed"]] = Field(default_factory=dict)
    stage_diagnostics: dict[str, list[GmailPhase1DiagnosticItem]] = Field(default_factory=dict)


class GmailPhase2ScrubbedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase2.scrubbed.v1"
    phase1_reference: GmailPhase1Reference
    message_id: str
    thread_id: str | None = None
    provider_message_id: str
    provider_thread_id: str | None = None
    rfc_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None
    selected_body_type: Literal["html", "text", "none"] = "none"
    selected_body_source: str | None = None
    selected_body_selection_path: str | None = None
    scrubbed_text: str = ""
    normalized_lines: list[str] = Field(default_factory=list)
    extracted_links: list[GmailPhase2Link] = Field(default_factory=list)
    applied_rules: list[str] = Field(default_factory=list)
    hidden_content_stripped: bool = False
    scrub_status: Literal["success", "partial", "failed"] = "failed"
    scrub_diagnostics: list[str] = Field(default_factory=list)
    transactional_quality: Literal["success", "partial", "failed"] = "failed"
    stage_statuses: dict[str, Literal["success", "partial", "failed"]] = Field(default_factory=dict)
    stage_diagnostics: dict[str, list[GmailPhase1DiagnosticItem]] = Field(default_factory=dict)
    scrub_metrics: GmailPhase2Metrics = Field(default_factory=GmailPhase2Metrics)
    normalization_metadata: GmailPhase2NormalizationMetadata | None = None


class GmailPhase3ProfileCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    profile_family: str
    profile_subtype: str
    vendor_identity: str | None = None
    sender_identity: str | None = None
    score: int = 0
    confidence_level: Literal["high", "medium", "low"] = "low"
    reasons: list[str] = Field(default_factory=list)


class GmailPhase3NormalizationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_detector_version: str
    taxonomy_version: str
    normalized_at: datetime


class GmailPhase3WorkingEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase3.working.v1"
    phase2_reference: GmailPhase2ScrubbedEmail
    message_id: str
    thread_id: str | None = None
    provider_message_id: str
    provider_thread_id: str | None = None
    rfc_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None
    sender_identity: str | None = None
    vendor_identity: str | None = None
    scrubbed_text: str = ""
    normalized_lines: list[str] = Field(default_factory=list)
    extracted_links: list[GmailPhase2Link] = Field(default_factory=list)
    candidate_profiles: list[GmailPhase3ProfileCandidate] = Field(default_factory=list)
    stage_statuses: dict[str, Literal["success", "partial", "failed"]] = Field(default_factory=dict)
    stage_diagnostics: dict[str, list[GmailPhase1DiagnosticItem]] = Field(default_factory=dict)


class GmailPhase3DetectedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase3.profile.v1"
    phase2_reference: GmailPhase2ScrubbedEmail
    message_id: str
    thread_id: str | None = None
    provider_message_id: str
    provider_thread_id: str | None = None
    rfc_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None
    sender_identity: str | None = None
    vendor_identity: str | None = None
    profile_id: str | None = None
    profile_family: str | None = None
    profile_subtype: str | None = None
    profile_confidence: float = 0.0
    profile_confidence_level: Literal["high", "medium", "low"] = "low"
    profile_status: Literal["success", "partial", "failed"] = "failed"
    candidate_profiles: list[GmailPhase3ProfileCandidate] = Field(default_factory=list)
    fallback_profiles: list[GmailPhase3ProfileCandidate] = Field(default_factory=list)
    profile_diagnostics: list[str] = Field(default_factory=list)
    stage_statuses: dict[str, Literal["success", "partial", "failed"]] = Field(default_factory=dict)
    stage_diagnostics: dict[str, list[GmailPhase1DiagnosticItem]] = Field(default_factory=dict)
    normalization_metadata: GmailPhase3NormalizationMetadata | None = None


class GmailPhase4ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str
    value: object | None = None
    source_method: str | None = None
    source_rule: str | None = None
    transforms_applied: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    is_valid: bool = True
    is_required: bool = False


class GmailPhase4TemplateCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    template_version: str
    profile_id: str
    score: int = 0
    reasons: list[str] = Field(default_factory=list)


class GmailPhase4NormalizationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extractor_version: str
    template_schema_version: str
    normalized_at: datetime


class GmailPhase4WorkingEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase4.working.v1"
    phase3_reference: GmailPhase3DetectedEmail
    message_id: str
    thread_id: str | None = None
    provider_message_id: str
    provider_thread_id: str | None = None
    rfc_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None
    sender_identity: str | None = None
    vendor_identity: str | None = None
    profile_id: str
    profile_family: str | None = None
    profile_subtype: str | None = None
    profile_confidence: float = 0.0
    scrubbed_text: str = ""
    normalized_lines: list[str] = Field(default_factory=list)
    extracted_links: list[GmailPhase2Link] = Field(default_factory=list)
    template_candidates: list[GmailPhase4TemplateCandidate] = Field(default_factory=list)
    stage_statuses: dict[str, Literal["success", "partial", "failed"]] = Field(default_factory=dict)
    stage_diagnostics: dict[str, list[GmailPhase1DiagnosticItem]] = Field(default_factory=dict)


class GmailPhase4ExtractedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "gmail.phase4.extracted.v1"
    phase3_reference: GmailPhase3DetectedEmail
    message_id: str
    thread_id: str | None = None
    provider_message_id: str
    provider_thread_id: str | None = None
    rfc_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    sender_domain: str | None = None
    sender_identity: str | None = None
    vendor_identity: str | None = None
    profile_id: str | None = None
    profile_family: str | None = None
    profile_subtype: str | None = None
    profile_confidence: float = 0.0
    template_id: str | None = None
    template_version: str | None = None
    extraction_status: Literal["success", "partial", "failed", "unresolved"] = "failed"
    extraction_confidence: float = 0.0
    extraction_confidence_level: Literal["high", "medium", "low"] = "low"
    extracted_fields: dict[str, GmailPhase4ExtractedField] = Field(default_factory=dict)
    field_diagnostics: list[str] = Field(default_factory=list)
    template_diagnostics: list[str] = Field(default_factory=list)
    fallback_templates: list[GmailPhase4TemplateCandidate] = Field(default_factory=list)
    ai_template_hook: dict[str, object] | None = None
    stage_statuses: dict[str, Literal["success", "partial", "failed"]] = Field(default_factory=dict)
    stage_diagnostics: dict[str, list[GmailPhase1DiagnosticItem]] = Field(default_factory=dict)
    normalization_metadata: GmailPhase4NormalizationMetadata | None = None


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


class GmailSenderReputationInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_count: int = 0
    classification_positive_count: int = 0
    classification_negative_count: int = 0
    spamhaus_clean_count: int = 0
    spamhaus_listed_count: int = 0


class GmailSenderReputationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    entity_type: Literal["email", "domain", "business_domain"]
    sender_value: str
    sender_email: str | None = None
    sender_domain: str | None = None
    group_domain: str | None = None
    reputation_state: Literal["trusted", "neutral", "risky", "blocked"] = "neutral"
    derived_rating: float = 0.0
    rating: float = 0.0
    manual_rating: float | None = None
    manual_rating_note: str | None = None
    manual_rating_updated_at: datetime | None = None
    inputs: GmailSenderReputationInputs = Field(default_factory=GmailSenderReputationInputs)
    last_seen_at: datetime | None = None
    updated_at: datetime | None = None


class GmailSenderReputationManualRatingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["email", "domain", "business_domain"]
    sender_value: str
    manual_rating: float | None = None
    note: str | None = None


class GmailShipmentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    record_id: str
    seller: str | None = None
    carrier: str | None = None
    order_number: str | None = None
    tracking_number: str | None = None
    domain: str | None = None
    last_known_status: str | None = None
    last_seen_at: datetime | None = None
    status_updated_at: datetime | None = None
    updated_at: datetime | None = None


class GmailShipmentScrubResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["skipped", "matched", "updated", "ignored"] = "skipped"
    reason_code: str
    matched_record_id: str | None = None
    matched_by: Literal["tracking_number", "order_number_domain", "order_number_seller"] | None = None
    sender_domain: str | None = None
    source_type: Literal["seller", "carrier", "unknown"] | None = None
    extracted_order_number: str | None = None
    extracted_tracking_number: str | None = None
    status_update_applied: bool = False


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
