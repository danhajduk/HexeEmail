from __future__ import annotations

from abc import ABC, abstractmethod

from providers.models import (
    OutboundSendRequest,
    ProviderAccountRecord,
    ProviderHealth,
    ProviderState,
    ProviderValidationResult,
)


class EmailProviderAdapter(ABC):
    provider_id: str

    @abstractmethod
    async def validate_static_config(self) -> ProviderValidationResult:
        raise NotImplementedError

    @abstractmethod
    async def get_provider_state(self) -> ProviderState:
        raise NotImplementedError

    @abstractmethod
    async def list_accounts(self) -> list[ProviderAccountRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_account_health(self, account_id: str) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    def get_enabled_status(self) -> bool:
        raise NotImplementedError

    async def send_email(self, request: OutboundSendRequest) -> None:
        raise NotImplementedError(f"{self.provider_id} does not support send_email yet")

    async def fetch_email(self, account_id: str) -> list[object]:
        raise NotImplementedError(f"{self.provider_id} does not support fetch_email yet")

    async def watch_mailbox(self, account_id: str) -> None:
        raise NotImplementedError(f"{self.provider_id} does not support watch_mailbox yet")
