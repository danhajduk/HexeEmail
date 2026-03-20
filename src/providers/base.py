from __future__ import annotations

from abc import ABC, abstractmethod

from providers.models import EmailProviderHealth


class EmailProviderAdapter(ABC):
    provider_id: str

    @abstractmethod
    async def health(self) -> EmailProviderHealth:
        raise NotImplementedError
