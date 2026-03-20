from __future__ import annotations

from dataclasses import dataclass, field

from config import AppConfig
from providers.base import EmailProviderAdapter
from providers.gmail.adapter import GmailProviderAdapter
from providers.models import ProviderId


@dataclass
class ProviderRegistry:
    config: AppConfig
    _providers: dict[str, EmailProviderAdapter] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.register_provider(GmailProviderAdapter(self.config.runtime_dir))

    def register_provider(self, adapter: EmailProviderAdapter) -> None:
        self._providers[str(adapter.provider_id)] = adapter

    def get_provider(self, provider_id: str | ProviderId) -> EmailProviderAdapter:
        key = str(provider_id)
        if key not in self._providers:
            raise KeyError(f"unsupported provider: {key}")
        return self._providers[key]

    def list_supported_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    def provider_ids(self) -> list[str]:
        return self.list_supported_providers()

    def build_enabled_adapters(self) -> dict[str, EmailProviderAdapter]:
        return {
            provider_id: adapter
            for provider_id, adapter in self._providers.items()
            if self._is_provider_enabled(provider_id)
        }

    def _is_provider_enabled(self, provider_id: str) -> bool:
        if provider_id == ProviderId.GMAIL.value:
            return self.config.providers.gmail.enabled
        if provider_id == ProviderId.SMTP.value:
            return self.config.providers.smtp.enabled
        if provider_id == ProviderId.IMAP.value:
            return self.config.providers.imap.enabled
        return False
