from __future__ import annotations

from pydantic import BaseModel


class GmailProviderModel(BaseModel):
    placeholder: str = "gmail-provider-phase1"
