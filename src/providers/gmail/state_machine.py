from __future__ import annotations

from datetime import UTC, datetime

from providers.gmail.account_store import GmailAccountStore
from providers.models import ProviderAccountRecord, ProviderAccountStatus, ProviderId


class ProviderAccountStateError(RuntimeError):
    pass


VALID_ACCOUNT_TRANSITIONS: dict[ProviderAccountStatus, set[ProviderAccountStatus]] = {
    "not_configured": {"oauth_pending"},
    "oauth_pending": {"token_exchanged", "revoked"},
    "token_exchanged": {"connected", "degraded", "revoked"},
    "connected": {"degraded", "revoked"},
    "degraded": {"connected", "revoked"},
    "revoked": {"oauth_pending"},
}


class GmailAccountStateMachine:
    def __init__(self, account_store: GmailAccountStore) -> None:
        self.account_store = account_store

    def ensure_account(self, account_id: str) -> ProviderAccountRecord:
        existing = self.account_store.load_account(account_id)
        if existing is not None:
            return existing
        created = ProviderAccountRecord(
            provider_id=ProviderId.GMAIL,
            account_id=account_id,
            status="not_configured",
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        return self.account_store.save_account(created)

    def transition(
        self,
        account_id: str,
        next_status: ProviderAccountStatus,
        *,
        last_error: str | None = None,
    ) -> ProviderAccountRecord:
        record = self.ensure_account(account_id)
        current = record.status
        if next_status != current and next_status not in VALID_ACCOUNT_TRANSITIONS[current]:
            raise ProviderAccountStateError(f"invalid provider account transition: {current} -> {next_status}")

        record.status = next_status
        record.last_error = last_error
        record.updated_at = datetime.now(UTC).replace(tzinfo=None)
        if next_status == "connected":
            record.last_connected_at = datetime.now(UTC).replace(tzinfo=None)
        return self.account_store.save_account(record)
