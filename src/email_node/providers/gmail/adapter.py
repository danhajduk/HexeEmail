from __future__ import annotations

from email_node.providers.base import EmailProviderAdapter
from email_node.providers.models import EmailProviderHealth, ProviderId


class GmailProviderAdapter(EmailProviderAdapter):
    provider_id = ProviderId.GMAIL.value

    async def health(self) -> EmailProviderHealth:
        return EmailProviderHealth(
            provider_id=ProviderId.GMAIL,
            status="placeholder",
            detail="Gmail adapter skeleton is registered but not yet connected.",
        )
