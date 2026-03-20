from __future__ import annotations

import pytest

from config import AppConfig
from providers.base import EmailProviderAdapter
from providers.models import EmailProviderHealth, ProviderId
from providers.registry import ProviderRegistry


class FakeGraphAdapter(EmailProviderAdapter):
    provider_id = ProviderId.GRAPH.value

    async def health(self) -> EmailProviderHealth:
        return EmailProviderHealth(provider_id=ProviderId.GRAPH, status="unknown")


def test_provider_registry_registers_gmail_by_default(runtime_dir):
    registry = ProviderRegistry(
        AppConfig(
            NODE_SOFTWARE_VERSION="0.1.0",
            NODE_NONCE="nonce-test",
            RUNTIME_DIR=runtime_dir,
        )
    )

    assert registry.list_supported_providers() == ["gmail"]
    assert registry.get_provider("gmail").provider_id == "gmail"


def test_provider_registry_allows_manual_registration(runtime_dir):
    registry = ProviderRegistry(
        AppConfig(
            NODE_SOFTWARE_VERSION="0.1.0",
            NODE_NONCE="nonce-test",
            RUNTIME_DIR=runtime_dir,
        )
    )

    registry.register_provider(FakeGraphAdapter())

    assert registry.list_supported_providers() == ["gmail", "graph"]
    assert registry.get_provider("graph").provider_id == "graph"


def test_provider_registry_rejects_unknown_provider(runtime_dir):
    registry = ProviderRegistry(
        AppConfig(
            NODE_SOFTWARE_VERSION="0.1.0",
            NODE_NONCE="nonce-test",
            RUNTIME_DIR=runtime_dir,
        )
    )

    with pytest.raises(KeyError):
        registry.get_provider("smtp")
