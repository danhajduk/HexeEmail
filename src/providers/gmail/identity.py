from __future__ import annotations

from datetime import UTC, datetime

import httpx

from logging_utils import get_logger
from providers.gmail.account_store import GmailAccountStore
from providers.gmail.models import GmailTokenRecord
from providers.models import ProviderAccountRecord, ProviderId


class GmailIdentityProbeError(RuntimeError):
    pass


LOGGER = get_logger(__name__)


class GmailIdentityProbeClient:
    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
    GMAIL_PROFILE_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

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

        payload = await self._fetch_profile_payload(headers, token_record.account_id)
        email = payload.get("email")
        if not isinstance(email, str) or not email:
            LOGGER.warning(
                "Gmail identity probe missing email",
                extra={"event_data": {"account_id": token_record.account_id}},
            )
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
        LOGGER.info(
            "Gmail identity probe succeeded",
            extra={"event_data": {"account_id": token_record.account_id, "email_address": email}},
        )
        return record

    async def _fetch_profile_payload(self, headers: dict[str, str], account_id: str) -> dict[str, object]:
        userinfo_response = await self._client.get(self.USERINFO_ENDPOINT, headers=headers)
        userinfo_payload = self._parse_json_payload(userinfo_response)
        if not userinfo_response.is_error and isinstance(userinfo_payload, dict):
            if isinstance(userinfo_payload.get("email"), str) and userinfo_payload.get("email"):
                return userinfo_payload

        profile_response = await self._client.get(self.GMAIL_PROFILE_ENDPOINT, headers=headers)
        profile_payload = self._parse_json_payload(profile_response)
        if profile_response.is_error or not isinstance(profile_payload, dict):
            LOGGER.warning("Gmail identity probe failed", extra={"event_data": {"account_id": account_id}})
            raise GmailIdentityProbeError("gmail identity probe failed")

        return {
            "email": profile_payload.get("emailAddress"),
            "id": profile_payload.get("emailAddress"),
            "name": None,
        }

    @staticmethod
    def _parse_json_payload(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise GmailIdentityProbeError("gmail identity probe returned invalid JSON") from exc

    async def aclose(self) -> None:
        await self._client.aclose()
