from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GmailRequestedScopes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scopes: list[str] = Field(default_factory=lambda: ["https://www.googleapis.com/auth/gmail.send"])

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        normalized = [scope.strip() for scope in value if scope.strip()]
        if not normalized:
            raise ValueError("at least one Gmail scope is required")
        return normalized


class GmailOAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oauth_client_type: Literal["desktop"] = "desktop"
    enabled: bool = False
    client_id: str | None = None
    client_secret_ref: str | None = None
    requested_scopes: GmailRequestedScopes = Field(default_factory=GmailRequestedScopes)


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
    redirect_uri: str
    code_verifier: str
    correlation_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=10))
    consumed_at: datetime | None = None
    authorization_url: str | None = None
