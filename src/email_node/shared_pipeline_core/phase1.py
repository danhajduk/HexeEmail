from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from providers.gmail.order_flow import GmailOrderPhase1Processor


@dataclass(slots=True)
class SharedPhase1NormalizeRequest:
    fetch_full_message_payload: Callable[[str, str], Awaitable[dict[str, object]]]
    account_id: str
    message_id: str


class SharedEmailPhase1Interface:
    def __init__(self, normalizer: GmailOrderPhase1Processor | None = None) -> None:
        self.normalizer = normalizer or GmailOrderPhase1Processor()

    async def normalize(self, request: SharedPhase1NormalizeRequest):
        return await self.normalizer.fetch_and_normalize_message(
            fetch_full_message_payload=request.fetch_full_message_payload,
            account_id=request.account_id,
            message_id=request.message_id,
        )
