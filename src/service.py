from __future__ import annotations

import asyncio
import contextlib
import socket
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from config import AppConfig
from core_client import CoreApiClient, FinalizeResponse, OnboardingSessionRequest
from logging_utils import get_logger
from models import (
    GmailConnectStartResponse,
    OnboardingStatusResponse,
    OperatorConfig,
    OperatorConfigInput,
    OperatorConfigResponse,
    RuntimeState,
    StatusResponse,
    TrustMaterial,
    UiBootstrapResponse,
)
from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.oauth import GmailOAuthSessionManager
from mqtt import MQTTManager
from providers.registry import ProviderRegistry
from state_store import OperatorConfigStore, RuntimeStateStore, StateCorruptionError, TrustMaterialStore
from version import __version__


LOGGER = get_logger(__name__)
TERMINAL_ONBOARDING_STATES = {"approved", "rejected", "expired", "consumed", "invalid"}


class NodeService:
    def __init__(
        self,
        config: AppConfig,
        *,
        core_client: CoreApiClient | None = None,
        mqtt_manager: MQTTManager | None = None,
    ) -> None:
        self.config = config
        self.state_store = RuntimeStateStore(config.state_file)
        self.operator_config_store = OperatorConfigStore(config.operator_config_file)
        self.trust_store = TrustMaterialStore(config.trust_material_file)
        self.core_client = core_client or CoreApiClient()
        self.mqtt_manager = mqtt_manager or MQTTManager(
            heartbeat_seconds=config.mqtt_heartbeat_seconds,
            on_heartbeat=self._record_heartbeat,
        )
        self.gmail_config_store = GmailProviderConfigStore(config.runtime_dir)
        self.gmail_oauth_manager = GmailOAuthSessionManager(config.runtime_dir)
        self.provider_registry = ProviderRegistry(config)
        self.operator_config = OperatorConfig(core_base_url=config.core_base_url, node_name=config.node_name)
        self.state = RuntimeState()
        self.trust_material: TrustMaterial | None = None
        self.polling_task: asyncio.Task | None = None
        self.live = True
        self.ready = False
        self.startup_error: str | None = None

    async def start(self) -> None:
        try:
            self.state = self.state_store.load()
            self.trust_material = self.trust_store.load()
            self.operator_config = self.operator_config_store.load(defaults=self.operator_config)
            self.operator_config = OperatorConfig(
                core_base_url=self._normalize_core_base_url(self.operator_config.core_base_url),
                node_name=self.operator_config.node_name,
            )
            self.operator_config_store.save(self.operator_config)
        except StateCorruptionError as exc:
            self.startup_error = str(exc)
            self.ready = False
            LOGGER.exception("Startup failed due to corrupted local state")
            return

        self.ready = True
        LOGGER.info(
            "Email node starting",
            extra={
                "event_data": {
                    "version": __version__,
                    "node_name": self.effective_node_name() or "(unset)",
                    "node_type": self.config.node_type,
                }
            },
        )
        await self._resume_runtime()

    async def stop(self) -> None:
        if self.polling_task is not None:
            self.polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.polling_task
        self.mqtt_manager.disconnect()
        await self.core_client.aclose()

    def required_inputs(self) -> list[str]:
        missing: list[str] = []
        if not self.operator_config.core_base_url:
            missing.append("core_base_url")
        if not self.operator_config.node_name:
            missing.append("node_name")
        return missing

    def effective_core_base_url(self) -> str | None:
        return self.operator_config.core_base_url

    def effective_node_name(self) -> str | None:
        return self.operator_config.node_name

    async def update_operator_config(self, payload: OperatorConfigInput) -> OperatorConfigResponse:
        if self.state.trust_state == "trusted":
            raise ValueError("cannot change onboarding configuration after trust activation")

        previous = self.operator_config.model_copy()
        next_config = OperatorConfig(
            core_base_url=self._normalize_core_base_url((payload.core_base_url or "").strip() or None),
            node_name=(payload.node_name or "").strip() or None,
        )
        self.operator_config = self.operator_config_store.save(next_config)

        if previous != self.operator_config:
            self._reset_onboarding_state()

        return self.operator_config_response()

    async def _resume_runtime(self) -> None:
        if self.state.trust_state == "trusted" and self.trust_material is not None:
            LOGGER.info("Trusted state detected, skipping onboarding")
            self._connect_mqtt_if_possible()
            return

        if self.state.onboarding_status == "pending" and self.state.onboarding_session_id:
            LOGGER.info("Pending onboarding session found, resuming finalize polling")
            self._ensure_polling()
            return

        if self.required_inputs():
            self.state.last_error = "Configuration required before onboarding can start"
            self.state_store.save(self.state)
            LOGGER.info(
                "Waiting for onboarding configuration",
                extra={"event_data": {"required_inputs": self.required_inputs()}},
            )
            return

        if self.state.onboarding_status == "not_started" or not self.state.onboarding_session_id:
            with contextlib.suppress(ValueError):
                await self.start_onboarding()
            return

        if self.state.onboarding_status in {"rejected", "expired", "invalid", "consumed"}:
            LOGGER.warning(
                "Terminal onboarding state found without trust, starting fresh onboarding",
                extra={"event_data": {"onboarding_status": self.state.onboarding_status}},
            )
            with contextlib.suppress(ValueError):
                await self.start_onboarding(force=True)
            return

        self.startup_error = "corrupted state: unable to determine startup path"
        self.ready = False

    async def start_onboarding(self, *, force: bool = False) -> OnboardingStatusResponse:
        if self.state.trust_state == "trusted":
            return self.onboarding_status()

        missing = self.required_inputs()
        if missing:
            self.state.last_error = "Missing required onboarding inputs"
            self.state_store.save(self.state)
            raise ValueError(f"missing required onboarding inputs: {', '.join(missing)}")

        if self.state.onboarding_status == "pending" and self.state.onboarding_session_id and not force:
            return self.onboarding_status()

        if force:
            self._reset_onboarding_state()

        correlation_id = str(uuid.uuid4())
        request = OnboardingSessionRequest(
            node_name=self.effective_node_name() or "",
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            protocol_version=self.config.onboarding_protocol_version,
            node_nonce=self.config.node_nonce,
            hostname=socket.gethostname(),
        )
        try:
            session = await self.core_client.create_onboarding_session(
                self.effective_core_base_url() or "",
                request,
                correlation_id,
            )
        except httpx.HTTPError as exc:
            self.state.last_error = self._format_core_error(exc)
            self.state_store.save(self.state)
            raise ValueError(self.state.last_error) from exc
        self.state.onboarding_session_id = session.session_id
        self.state.approval_url = session.approval_url
        self.state.onboarding_status = "pending"
        self.state.trust_state = "pending"
        self.state.onboarding_expires_at = datetime.fromisoformat(session.expires_at) if session.expires_at else None
        self.state.last_error = None
        self.state_store.save(self.state)
        LOGGER.info(
            "Onboarding session created",
            extra={"event_data": {"session_id": session.session_id}},
        )
        LOGGER.info(
            "Awaiting operator approval",
            extra={"event_data": {"approval_url": session.approval_url}},
        )
        print(f"Approval URL: {session.approval_url}")
        self._ensure_polling()
        return self.onboarding_status()

    def _reset_onboarding_state(self) -> None:
        if self.polling_task is not None and not self.polling_task.done():
            self.polling_task.cancel()
        self.state.onboarding_session_id = None
        self.state.approval_url = None
        self.state.onboarding_status = "not_started"
        self.state.onboarding_expires_at = None
        self.state.node_id = None
        self.state.paired_core_id = None
        self.state.trust_state = "untrusted"
        self.state.trust_token_present = False
        self.state.mqtt_credentials_present = False
        self.state.operational_mqtt_host = None
        self.state.operational_mqtt_port = None
        self.state.last_finalize_status = None
        self.state.last_error = None
        self.state.trusted_at = None
        self.state.last_poll_at = None
        self.state_store.save(self.state)

    def _normalize_core_base_url(self, value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value)
        if not parsed.scheme:
            return f"http://{value}"
        return value.rstrip("/")

    def _format_core_error(self, exc: httpx.HTTPError) -> str:
        base_url = self.effective_core_base_url() or "configured Core URL"
        if isinstance(exc, httpx.ConnectError):
            return f"Unable to reach Core at {base_url}. Check the host, port, and network."
        if isinstance(exc, httpx.TimeoutException):
            return f"Timed out while contacting Core at {base_url}."
        if isinstance(exc, httpx.HTTPStatusError):
            detail_message = self._extract_core_error_message(exc.response)
            if detail_message:
                return detail_message
            return f"Core returned {exc.response.status_code} during onboarding start."
        if isinstance(exc, httpx.UnsupportedProtocol):
            return f"Core URL must include a valid host. Current value: {base_url}"
        return f"Failed to contact Core at {base_url}: {exc.__class__.__name__}"

    def _extract_core_error_message(self, response: httpx.Response) -> str | None:
        try:
            body = response.json()
        except ValueError:
            return None

        if not isinstance(body, dict):
            return None

        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict):
            message = detail.get("message")
            error = detail.get("error")
            if error == "duplicate_active_session":
                return "Core already has an active onboarding session for this node. Resume the existing session or clear it in Core before starting again."
            if isinstance(message, str) and message:
                return message
        return None

    def _ensure_polling(self) -> None:
        if self.polling_task is None or self.polling_task.done():
            self.polling_task = asyncio.create_task(self._poll_finalize_loop())

    async def _poll_finalize_loop(self) -> None:
        while self.state.onboarding_session_id:
            correlation_id = str(uuid.uuid4())
            finalize = await self.core_client.finalize_onboarding(
                self.effective_core_base_url() or "",
                self.state.onboarding_session_id,
                self.config.node_nonce,
                correlation_id,
            )
            self._apply_finalize_result(finalize)
            if finalize.onboarding_status in TERMINAL_ONBOARDING_STATES:
                return
            await asyncio.sleep(self.config.onboarding_poll_interval_seconds)

    def _apply_finalize_result(self, finalize: FinalizeResponse) -> None:
        self.state.last_poll_at = datetime.now(UTC).replace(tzinfo=None)
        self.state.last_finalize_status = finalize.onboarding_status
        self.state.onboarding_status = finalize.onboarding_status  # type: ignore[assignment]
        self.state.last_error = finalize.message

        LOGGER.info(
            "Finalize result received",
            extra={
                "event_data": {
                    "session_id": self.state.onboarding_session_id,
                    "onboarding_status": finalize.onboarding_status,
                }
            },
        )

        if finalize.onboarding_status == "approved" and finalize.activation is not None:
            trust_material = TrustMaterial.model_validate(finalize.activation.model_dump())
            self.trust_store.save(trust_material)
            self.trust_material = trust_material
            self.state.node_id = trust_material.node_id
            self.state.paired_core_id = trust_material.paired_core_id
            self.state.trust_state = "trusted"
            self.state.trust_token_present = True
            self.state.mqtt_credentials_present = True
            self.state.operational_mqtt_host = trust_material.operational_mqtt_host
            self.state.operational_mqtt_port = trust_material.operational_mqtt_port
            self.state.trusted_at = datetime.now(UTC).replace(tzinfo=None)
            self.state_store.save(self.state)
            LOGGER.info(
                "Trust activated",
                extra={
                    "event_data": {
                        "node_id": trust_material.node_id,
                        "paired_core_id": trust_material.paired_core_id,
                    }
                },
            )
            self._connect_mqtt_if_possible()
            return

        if finalize.onboarding_status in {"rejected", "expired", "consumed", "invalid"}:
            self.state.trust_state = finalize.onboarding_status  # type: ignore[assignment]
        else:
            self.state.trust_state = "pending"

        self.state_store.save(self.state)

    def _connect_mqtt_if_possible(self) -> None:
        if self.trust_material is None:
            return
        self.mqtt_manager.connect(self.trust_material)

    def _record_heartbeat(self) -> None:
        self.state.last_heartbeat_at = datetime.now(UTC).replace(tzinfo=None)
        self.state_store.save(self.state)

    def health_snapshot(self) -> dict[str, object]:
        return {
            "live": self.live,
            "ready": self.ready,
            "version": __version__,
            "startup_error": self.startup_error,
        }

    def operator_config_response(self) -> OperatorConfigResponse:
        return OperatorConfigResponse(
            core_base_url=self.effective_core_base_url() or "",
            node_name=self.effective_node_name() or "",
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            api_port=self.config.api_port,
            ui_port=self.config.ui_port,
        )

    def onboarding_status(self) -> OnboardingStatusResponse:
        return OnboardingStatusResponse(
            node_name=self.effective_node_name() or "",
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            session_id=self.state.onboarding_session_id,
            approval_url=self.state.approval_url,
            onboarding_status=self.state.onboarding_status,
            trust_state=self.state.trust_state,
            node_id=self.state.node_id,
            expires_at=self.state.onboarding_expires_at,
            last_error=self.state.last_error,
            required_inputs=self.required_inputs(),
        )

    def status(self) -> StatusResponse:
        return StatusResponse(
            node_name=self.effective_node_name() or "",
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            trust_state=self.state.trust_state,
            node_id=self.state.node_id,
            mqtt_connection_status=self.mqtt_manager.status.state,
            onboarding_status=self.state.onboarding_status,
            providers=self.provider_registry.provider_ids(),
            required_inputs=self.required_inputs(),
        )

    def ui_bootstrap(self) -> UiBootstrapResponse:
        required_inputs = self.required_inputs()
        return UiBootstrapResponse(
            config=self.operator_config_response(),
            onboarding=self.onboarding_status(),
            status=self.status(),
            required_inputs=required_inputs,
            can_start_onboarding=not required_inputs and self.state.trust_state != "trusted",
        )

    async def start_gmail_connect(self, account_id: str, *, correlation_id: str | None = None) -> GmailConnectStartResponse:
        if self.state.trust_state != "trusted":
            raise ValueError("gmail provider activation requires a trusted node")

        try:
            oauth_config = self.gmail_config_store.load()
        except GmailProviderConfigError as exc:
            raise ValueError(str(exc)) from exc

        validation = self.gmail_config_store.validate(oauth_config)
        if not validation.ok:
            raise ValueError(f"gmail provider configuration is incomplete: {', '.join(validation.missing_fields)}")
        if not oauth_config.enabled:
            raise ValueError("gmail provider is disabled")

        session = self.gmail_oauth_manager.create_connect_session(
            account_id,
            oauth_config,
            correlation_id=correlation_id,
        )
        LOGGER.info(
            "Gmail connect flow started",
            extra={
                "event_data": {
                    "provider_id": "gmail",
                    "account_id": account_id,
                    "state": session.state,
                    "expires_at": session.expires_at.isoformat(),
                }
            },
        )
        return GmailConnectStartResponse(
            provider_id="gmail",
            account_id=account_id,
            connect_url=session.authorization_url or "",
            expires_at=session.expires_at,
        )
