from __future__ import annotations

from datetime import UTC, datetime

import httpx

from providers.gmail.account_store import GmailAccountStore
from providers.gmail.models import GmailTokenRecord
from providers.models import ProviderAccountRecord, ProviderId


class GmailIdentityProbeError(RuntimeError):
    pass


class GmailIdentityProbeClient:
    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"

    def __init__(
        self,
        account_store: GmailAccountStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.account_store = account_store
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def probe_identity(
        self,
        token_record: GmailTokenRecord,
        *,
        correlation_id: str | None = None,
    ) -> ProviderAccountRecord:
        headers = {"Authorization": f"Bearer {token_record.access_token}"}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        response = await self._client.get(self.USERINFO_ENDPOINT, headers=headers)
        try:
            payload = response.json()
        except ValueError as exc:
            raise GmailIdentityProbeError("gmail identity probe returned invalid JSON") from exc

        if response.is_error or not isinstance(payload, dict):
            raise GmailIdentityProbeError("gmail identity probe failed")

        email = payload.get("email")
        if not isinstance(email, str) or not email:
            raise GmailIdentityProbeError("gmail identity probe did not return an email address")

        external_account_id = payload.get("id")
        existing = self.account_store.load_account(token_record.account_id)
        record = ProviderAccountRecord(
            provider_id=ProviderId.GMAIL,
            account_id=token_record.account_id,
            status=existing.status if existing is not None else "token_exchanged",
            email_address=email,
            display_name=payload.get("name") if isinstance(payload.get("name"), str) else None,
            external_account_id=external_account_id if isinstance(external_account_id, str) else None,
            last_error=existing.last_error if existing is not None else None,
            last_connected_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.account_store.save_account(record)
        return record

    async def aclose(self) -> None:
        await self._client.aclose()
