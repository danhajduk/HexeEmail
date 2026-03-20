from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx

from providers.gmail.models import GmailOAuthConfig, GmailTokenRecord


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
