from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx

from providers.gmail.account_store import GmailAccountStore
from providers.gmail.models import GmailOAuthConfig, GmailTokenRecord
from providers.gmail.state_machine import GmailAccountStateMachine
from providers.gmail.token_store import GmailTokenStore


class GmailTokenExchangeError(RuntimeError):
    pass


class GmailTokenExchangeClient:
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def exchange_authorization_code(
        self,
        oauth_config: GmailOAuthConfig,
        *,
        account_id: str,
        code: str,
        correlation_id: str | None = None,
    ) -> GmailTokenRecord:
        client_secret = self._resolve_client_secret(oauth_config.client_secret_ref)
        headers = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        response = await self._client.post(
            self.TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": oauth_config.client_id or "",
                "client_secret": client_secret,
                "redirect_uri": oauth_config.redirect_uri or "",
                "grant_type": "authorization_code",
            },
            headers=headers,
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GmailTokenExchangeError("gmail token exchange returned invalid JSON") from exc

        if response.is_error:
            error = payload.get("error") if isinstance(payload, dict) else None
            description = payload.get("error_description") if isinstance(payload, dict) else None
            if error == "invalid_grant":
                raise GmailTokenExchangeError(description or "gmail token exchange rejected the authorization code")
            raise GmailTokenExchangeError(description or f"gmail token exchange failed with status {response.status_code}")

        if not isinstance(payload, dict):
            raise GmailTokenExchangeError("gmail token exchange returned an invalid payload")

        expires_in = payload.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int):
            expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=expires_in)

        granted_scope_value = payload.get("scope")
        granted_scopes = granted_scope_value.split(" ") if isinstance(granted_scope_value, str) else []

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GmailTokenExchangeError("gmail token exchange did not return an access token")

        refresh_token = payload.get("refresh_token")
        token_type = payload.get("token_type")
        return GmailTokenRecord(
            account_id=account_id,
            access_token=access_token,
            refresh_token=refresh_token if isinstance(refresh_token, str) else None,
            token_type=token_type if isinstance(token_type, str) and token_type else "Bearer",
            expires_at=expires_at,
            granted_scopes=granted_scopes,
        )

    async def refresh_access_token(
        self,
        oauth_config: GmailOAuthConfig,
        *,
        account_id: str,
        refresh_token: str,
        correlation_id: str | None = None,
    ) -> GmailTokenRecord:
        client_secret = self._resolve_client_secret(oauth_config.client_secret_ref)
        headers = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        response = await self._client.post(
            self.TOKEN_ENDPOINT,
            data={
                "client_id": oauth_config.client_id or "",
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers=headers,
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GmailTokenExchangeError("gmail token refresh returned invalid JSON") from exc

        if response.is_error:
            error = payload.get("error") if isinstance(payload, dict) else None
            description = payload.get("error_description") if isinstance(payload, dict) else None
            if error == "invalid_grant":
                raise GmailTokenExchangeError(
                    f"invalid_grant: {description}" if description else "gmail refresh token is invalid or revoked"
                )
            raise GmailTokenExchangeError(description or f"gmail token refresh failed with status {response.status_code}")

        return self._normalize_token_payload(payload, account_id=account_id, fallback_refresh_token=refresh_token)

    async def refresh_if_needed(
        self,
        oauth_config: GmailOAuthConfig,
        *,
        account_id: str,
        token_store: GmailTokenStore,
        account_store: GmailAccountStore,
        threshold_seconds: int = 300,
        correlation_id: str | None = None,
    ) -> GmailTokenRecord | None:
        state_machine = GmailAccountStateMachine(account_store)
        token_record = token_store.load_token(account_id)
        if token_record is None:
            return None
        if token_record.expires_at is None:
            return token_record

        refresh_cutoff = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=threshold_seconds)
        if token_record.expires_at > refresh_cutoff:
            return token_record
        if not token_record.refresh_token:
            if account_store.load_account(account_id) is not None:
                state_machine.transition(account_id, "degraded", last_error="refresh token missing")
            return token_record

        try:
            refreshed = await self.refresh_access_token(
                oauth_config,
                account_id=account_id,
                refresh_token=token_record.refresh_token,
                correlation_id=correlation_id,
            )
        except GmailTokenExchangeError as exc:
            if account_store.load_account(account_id) is not None:
                next_status = "revoked" if "invalid" in str(exc).lower() or "revoked" in str(exc).lower() else "degraded"
                state_machine.transition(account_id, next_status, last_error=str(exc))
            raise

        token_store.save_token(account_id, refreshed)
        account_record = account_store.load_account(account_id)
        if account_record is not None and account_record.status not in {"connected", "token_exchanged"}:
            state_machine.transition(account_id, "token_exchanged")
        return refreshed

    async def aclose(self) -> None:
        await self._client.aclose()

    def _resolve_client_secret(self, client_secret_ref: str | None) -> str:
        if not client_secret_ref:
            raise GmailTokenExchangeError("gmail client secret reference is required")
        if client_secret_ref.startswith("env:"):
            env_name = client_secret_ref.removeprefix("env:")
            value = os.environ.get(env_name)
            if not value:
                raise GmailTokenExchangeError(f"gmail client secret environment variable is missing: {env_name}")
            return value
        return client_secret_ref

    def _normalize_token_payload(
        self,
        payload: object,
        *,
        account_id: str,
        fallback_refresh_token: str | None = None,
    ) -> GmailTokenRecord:
        if not isinstance(payload, dict):
            raise GmailTokenExchangeError("gmail token exchange returned an invalid payload")

        expires_in = payload.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int):
            expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=expires_in)

        granted_scope_value = payload.get("scope")
        granted_scopes = granted_scope_value.split(" ") if isinstance(granted_scope_value, str) else []

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GmailTokenExchangeError("gmail token exchange did not return an access token")

        refresh_token = payload.get("refresh_token")
        token_type = payload.get("token_type")
        return GmailTokenRecord(
            account_id=account_id,
            access_token=access_token,
            refresh_token=refresh_token if isinstance(refresh_token, str) else fallback_refresh_token,
            token_type=token_type if isinstance(token_type, str) and token_type else "Bearer",
            expires_at=expires_at,
            granted_scopes=granted_scopes,
        )
