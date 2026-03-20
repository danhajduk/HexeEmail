from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ProviderId(StrEnum):
    GMAIL = "gmail"
    SMTP = "smtp"
    IMAP = "imap"
    GRAPH = "graph"


class EmailProviderConfig(BaseModel):
    provider_id: ProviderId
    enabled: bool = False


class EmailProviderHealth(BaseModel):
    provider_id: ProviderId
    status: str
    detail: str | None = None


class OutboundSendRequest(BaseModel):
    provider_id: ProviderId
    recipient: str
    subject: str
    text_body: str


class ProviderCapabilities(BaseModel):
    provider_id: ProviderId
    supports_send: bool = False
    supports_receive: bool = False
    supports_oauth: bool = False
