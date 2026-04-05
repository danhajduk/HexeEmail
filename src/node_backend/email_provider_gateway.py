from __future__ import annotations

from typing import Any


class EmailProviderGateway:
    def __init__(self, service: Any) -> None:
        self.service = service

    def gmail_adapter(self):
        return self.service.provider_registry.get_provider("gmail")

    def assert_enabled(self) -> None:
        if not self.service.runtime.runtime_provider_calls_enabled():
            raise ValueError(self.service.runtime.runtime_provider_disabled_message())

    async def gmail_get_account_health(self, account_id: str):
        self.assert_enabled()
        return await self.gmail_adapter().get_account_health(account_id)

    async def gmail_refresh_mailbox_status(
        self,
        account_id: str,
        *,
        store_unread_messages: bool = True,
        correlation_id: str | None = None,
    ):
        self.assert_enabled()
        return await self.gmail_adapter().refresh_mailbox_status(
            account_id,
            store_unread_messages=store_unread_messages,
            correlation_id=correlation_id,
        )

    async def gmail_available_labels(self, account_id: str, *, refresh: bool = True) -> dict[str, object]:
        self.assert_enabled()
        return await self.gmail_adapter().available_labels(account_id, refresh=refresh)

    async def gmail_fetch_messages_for_window(
        self,
        account_id: str,
        *,
        window: str,
        reason: str = "manual",
        slot_key: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        self.assert_enabled()
        return await self.gmail_adapter().fetch_messages_for_window(
            account_id,
            window=window,
            reason=reason,
            slot_key=slot_key,
            correlation_id=correlation_id,
        )

    async def gmail_fetch_full_message_text(self, account_id: str, message_id: str) -> dict[str, object]:
        self.assert_enabled()
        return await self.gmail_adapter().fetch_full_message_text(account_id, message_id)

    async def gmail_fetch_full_message_payload(self, account_id: str, message_id: str) -> dict[str, object]:
        self.assert_enabled()
        return await self.gmail_adapter().fetch_full_message_payload(account_id, message_id)

    async def gmail_complete_oauth_callback(
        self,
        account_id: str,
        code: str,
        *,
        redirect_uri: str,
        code_verifier: str,
        correlation_id: str | None = None,
    ):
        self.assert_enabled()
        return await self.gmail_adapter().complete_oauth_callback(
            account_id,
            code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            correlation_id=correlation_id,
        )
