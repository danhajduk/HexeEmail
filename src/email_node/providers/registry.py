from __future__ import annotations

from dataclasses import dataclass

from email_node.config import AppConfig
from email_node.providers.gmail.adapter import GmailProviderAdapter
from email_node.providers.models import ProviderId


@dataclass
class ProviderRegistry:
    config: AppConfig

    def provider_ids(self) -> list[str]:
        return [provider.value for provider in ProviderId]

    def build_enabled_adapters(self) -> dict[str, object]:
        adapters: dict[str, object] = {}
        if self.config.providers.gmail.enabled:
            adapters[ProviderId.GMAIL.value] = GmailProviderAdapter()
        return adapters
