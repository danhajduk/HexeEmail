from __future__ import annotations

import asyncio
import contextlib
import re
import socket
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
from config import AppConfig
from core.capability_client import CapabilityClient, CapabilityDeclarationResult, CapabilityManifestBuilder
from core.governance_client import GovernanceClient, GovernanceSnapshot
from core.readiness import OperationalReadinessEvaluator
from core_client import CoreApiClient, FinalizeResponse, OnboardingSessionRequest
from logging_utils import get_logger
from models import (
    GmailConnectStartResponse,
    GmailOAuthCallbackResponse,
    MqttHealthResponse,
    OnboardingStatusResponse,
    OperatorConfig,
    OperatorConfigInput,
    OperatorConfigResponse,
    RuntimeState,
    StatusResponse,
    TrustMaterial,
    UiBootstrapResponse,
)
from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.models import GmailManualClassificationBatchInput, GmailOAuthConfig
from providers.gmail.oauth import GmailOAuthSessionManager
from providers.gmail.token_client import GmailTokenExchangeClient, GmailTokenExchangeError
from mqtt import MQTTManager
from providers.registry import ProviderRegistry
from state_store import OperatorConfigStore, RuntimeStateStore, StateCorruptionError, TrustMaterialStore
from version import __version__


LOGGER = get_logger(__name__)
TERMINAL_ONBOARDING_STATES = {"approved", "rejected", "expired", "consumed", "invalid"}
CORE_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
AVAILABLE_TASK_CAPABILITIES = [
    "task.classification",
    "task.summarization",
    "task.tracking",
]


class NodeService:
    def __init__(
        self,
        config: AppConfig,
        *,
        core_client: CoreApiClient | None = None,
        mqtt_manager: MQTTManager | None = None,
        gmail_token_client: GmailTokenExchangeClient | None = None,
        capability_client: CapabilityClient | None = None,
        governance_client: GovernanceClient | None = None,
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
        self.gmail_token_client = gmail_token_client or GmailTokenExchangeClient()
        self.capability_client = capability_client or CapabilityClient()
        self.governance_client = governance_client or GovernanceClient()
        self.capability_manifest_builder = CapabilityManifestBuilder()
        self.readiness_evaluator = OperationalReadinessEvaluator()
        self.provider_registry = ProviderRegistry(config)
        self.provider_registry.register_provider(GmailProviderAdapter(config.runtime_dir, token_client=self.gmail_token_client))
        self.operator_config = OperatorConfig(core_base_url=config.core_base_url, node_name=config.node_name)
        self.state = RuntimeState()
        self.trust_material: TrustMaterial | None = None
        self.polling_task: asyncio.Task | None = None
        self.gmail_status_task: asyncio.Task | None = None
        self.gmail_fetch_task: asyncio.Task | None = None
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
                selected_task_capabilities=self._normalize_selected_task_capabilities(
                    self.operator_config.selected_task_capabilities
                ),
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
        if self.config.gmail_status_poll_on_startup:
            self._ensure_gmail_status_polling()
        if self.config.gmail_fetch_poll_on_startup:
            self._ensure_gmail_fetch_polling()

    async def stop(self) -> None:
        if self.polling_task is not None:
            self.polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.polling_task
        if self.gmail_status_task is not None:
            self.gmail_status_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.gmail_status_task
        if self.gmail_fetch_task is not None:
            self.gmail_fetch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.gmail_fetch_task
        self.mqtt_manager.disconnect()
        for provider_id in self.provider_registry.provider_ids():
            await self.provider_registry.get_provider(provider_id).aclose()
        await self.capability_client.aclose()
        await self.governance_client.aclose()
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

    def selected_task_capabilities(self) -> list[str]:
        return list(self.operator_config.selected_task_capabilities)

    async def update_operator_config(self, payload: OperatorConfigInput) -> OperatorConfigResponse:
        previous = self.operator_config.model_copy()
        next_config = OperatorConfig(
            core_base_url=self._normalize_core_base_url((payload.core_base_url or "").strip() or None),
            node_name=(payload.node_name or "").strip() or None,
            selected_task_capabilities=self._normalize_selected_task_capabilities(payload.selected_task_capabilities),
        )

        if self.state.trust_state == "trusted" and (
            next_config.core_base_url != previous.core_base_url or next_config.node_name != previous.node_name
        ):
            raise ValueError("cannot change onboarding configuration after trust activation")

        self.operator_config = self.operator_config_store.save(next_config)

        if (
            previous.core_base_url != self.operator_config.core_base_url
            or previous.node_name != self.operator_config.node_name
        ):
            self._reset_onboarding_state()
        elif previous.selected_task_capabilities != self.operator_config.selected_task_capabilities:
            await self._refresh_post_trust_state()

        return self.operator_config_response()

    async def restart_setup(self, payload: OperatorConfigInput | None = None) -> OnboardingStatusResponse:
        self._clear_trust_and_onboarding_state()

        if payload is not None:
            next_config = OperatorConfig(
                core_base_url=self._normalize_core_base_url((payload.core_base_url or "").strip() or None),
                node_name=(payload.node_name or "").strip() or None,
                selected_task_capabilities=self._normalize_selected_task_capabilities(payload.selected_task_capabilities),
            )
            self.operator_config = self.operator_config_store.save(next_config)

        if self.required_inputs():
            self.state.last_error = "Configuration required before onboarding can start"
            self.state_store.save(self.state)
            return self.onboarding_status()

        return await self.start_onboarding()

    async def _resume_runtime(self) -> None:
        if self.state.trust_state == "trusted" and self.trust_material is not None:
            LOGGER.info("Trusted state detected, skipping onboarding")
            await self._refresh_post_trust_state()
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
            hostname=self._resolve_advertised_host(),
            ui_endpoint=self._advertised_ui_endpoint(),
            api_base_url=self._advertised_api_base_url(),
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

    async def restart_onboarding(self) -> OnboardingStatusResponse:
        return await self.start_onboarding(force=True)

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

    def _clear_trust_and_onboarding_state(self) -> None:
        self._reset_onboarding_state()
        self.trust_store.clear()
        self.trust_material = None
        self.mqtt_manager.disconnect()

    def _normalize_core_base_url(self, value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value)
        if not parsed.scheme:
            return f"http://{value}"
        return value.rstrip("/")

    def _normalize_selected_task_capabilities(self, values: list[str] | None) -> list[str]:
        available = set(AVAILABLE_TASK_CAPABILITIES)
        normalized: list[str] = []
        for value in values or []:
            candidate = str(value or "").strip()
            if candidate and candidate in available and candidate not in normalized:
                normalized.append(candidate)
        return normalized

    def _capability_setup_summary(self, provider_overview: dict[str, object]) -> dict[str, object]:
        provider_summaries = provider_overview.get("providers") if isinstance(provider_overview, dict) else {}
        connected_providers = [
            provider_id
            for provider_id, summary in (provider_summaries.items() if isinstance(provider_summaries, dict) else [])
            if isinstance(summary, dict) and summary.get("provider_state") == "connected"
        ]
        selected_capabilities = self.selected_task_capabilities()
        trust_valid = self.state.trust_state == "trusted"
        node_identity_valid = bool(self.effective_node_name())
        provider_selection_valid = bool(connected_providers)
        task_capability_selection_valid = bool(selected_capabilities)
        core_runtime_context_valid = bool(self.effective_core_base_url() and self.state.node_id)
        blocking_reasons: list[str] = []
        if not trust_valid:
            blocking_reasons.append("trust not active")
        if not node_identity_valid:
            blocking_reasons.append("node identity is incomplete")
        if not provider_selection_valid:
            blocking_reasons.append("connect Gmail before declaring capabilities")
        if not task_capability_selection_valid:
            blocking_reasons.append("select at least one task capability")
        if not core_runtime_context_valid:
            blocking_reasons.append("core runtime context is not ready")

        return {
            "readiness_flags": {
                "trust_state_valid": trust_valid,
                "node_identity_valid": node_identity_valid,
                "provider_selection_valid": provider_selection_valid,
                "task_capability_selection_valid": task_capability_selection_valid,
                "core_runtime_context_valid": core_runtime_context_valid,
            },
            "provider_selection": {
                "configured": provider_selection_valid,
                "enabled_count": len(connected_providers),
                "enabled": connected_providers,
                "supported": {
                    "cloud": list(provider_overview.get("supported_providers") or []),
                    "local": [],
                    "future": [],
                },
            },
            "task_capability_selection": {
                "configured": task_capability_selection_valid,
                "selected_count": len(selected_capabilities),
                "selected": selected_capabilities,
                "available": list(AVAILABLE_TASK_CAPABILITIES),
            },
            "blocking_reasons": blocking_reasons,
            "declaration_allowed": not blocking_reasons,
        }

    def _resolve_advertised_host(self) -> str:
        targets: list[tuple[str, int]] = []
        core_host = urlparse(self.effective_core_base_url() or "").hostname
        if core_host:
            targets.append((core_host, 80))
        targets.append(("8.8.8.8", 80))

        for host, port in targets:
            with contextlib.suppress(OSError):
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect((host, port))
                    address = sock.getsockname()[0]
                    if address and not address.startswith("127."):
                        return address

        with contextlib.suppress(OSError):
            address = socket.gethostbyname(socket.gethostname())
            if address and not address.startswith("127."):
                return address

        return socket.gethostname()

    def _advertised_api_base_url(self) -> str:
        host = self._resolve_advertised_host()
        return f"http://{host}:{self.config.api_port}/api"

    def _advertised_ui_endpoint(self) -> str:
        host = self._resolve_advertised_host()
        return f"http://{host}:{self.config.ui_port}"

    async def _resolve_gmail_oauth_core_id(self, oauth_config: GmailOAuthConfig) -> str:
        for candidate in (
            self._extract_hexe_core_uuid(oauth_config.redirect_uri),
            self._extract_hexe_core_uuid(self.state.approval_url),
            self._extract_hexe_core_uuid(self.effective_core_base_url()),
            self._normalize_platform_core_id(self.state.paired_core_id),
        ):
            if candidate:
                return candidate

        core_base_url = self.effective_core_base_url()
        if core_base_url:
            with contextlib.suppress(httpx.HTTPError, ValueError):
                identity = await self.core_client.get_platform_identity(core_base_url)
                candidate = self._normalize_platform_core_id(identity.core_id)
                if candidate:
                    return candidate

        raise ValueError("unable to resolve Core UUID for Gmail OAuth state")

    def _normalize_platform_core_id(self, value: str | None) -> str | None:
        candidate = str(value or "").strip().lower()
        if CORE_ID_PATTERN.fullmatch(candidate):
            return candidate
        return None

    def _extract_hexe_core_uuid(self, value: str | None) -> str | None:
        if not value:
            return None
        host = urlparse(value).hostname or ""
        if host.endswith(".hexe-ai.com"):
            candidate = host.removesuffix(".hexe-ai.com")
            if candidate and candidate != "hexe-ai":
                return candidate
        return None

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
            asyncio.create_task(self._refresh_post_trust_state())
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

    def _mqtt_health_snapshot(self) -> MqttHealthResponse:
        stale_after_s = max(30, int(self.config.node_status_stale_after_s))
        inactive_after_s = max(int(self.config.node_status_inactive_after_s), stale_after_s + 1)
        connection_state = self.mqtt_manager.status.state
        last_status_report_at = self.state.last_heartbeat_at
        status_age_s: int | None = None
        status_freshness_state = "unknown"
        health_status: str | None = None
        status_stale = False
        status_inactive = False

        if last_status_report_at is not None:
            age_delta = datetime.now(UTC).replace(tzinfo=None) - last_status_report_at
            status_age_s = max(0, int(age_delta.total_seconds()))
            if status_age_s > inactive_after_s:
                status_inactive = True
                status_stale = True
                status_freshness_state = "inactive"
                health_status = "offline"
            elif status_age_s > stale_after_s:
                status_stale = True
                status_freshness_state = "stale"
                health_status = "degraded"
            else:
                status_freshness_state = "fresh"
                health_status = "connected" if connection_state == "connected" else "degraded"
        elif connection_state == "connected":
            health_status = "unknown"
        elif connection_state in {"connecting", "reconnecting"}:
            health_status = "degraded"
        else:
            health_status = "offline"
            status_freshness_state = "inactive"
            status_inactive = True
            status_stale = True

        return MqttHealthResponse(
            health_status=health_status,
            status_freshness_state=status_freshness_state,
            status_stale=status_stale,
            status_inactive=status_inactive,
            status_age_s=status_age_s,
            status_stale_after_s=stale_after_s,
            status_inactive_after_s=inactive_after_s,
            last_status_report_at=last_status_report_at,
        )

    def health_snapshot(self) -> dict[str, object]:
        ready = self.ready and (self.state.trust_state != "trusted" or self.state.operational_readiness)
        return {
            "live": self.live,
            "ready": ready,
            "version": __version__,
            "startup_error": self.startup_error,
            "operational_readiness": self.state.operational_readiness,
            "capability_declaration_status": self.state.capability_declaration_status,
            "governance_sync_status": self.state.governance_sync_status,
        }

    def operator_config_response(self) -> OperatorConfigResponse:
        return OperatorConfigResponse(
            core_base_url=self.effective_core_base_url() or "",
            node_name=self.effective_node_name() or "",
            selected_task_capabilities=self.selected_task_capabilities(),
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            api_port=self.config.api_port,
            ui_port=self.config.ui_port,
        )

    async def capability_config_response(self) -> dict[str, object]:
        provider_overview = await self._provider_status_snapshot_async()
        capability_setup = self._capability_setup_summary(provider_overview)
        selection = capability_setup.get("task_capability_selection", {})
        return {
            "selected_task_capabilities": self.selected_task_capabilities(),
            "available_task_capabilities": list(AVAILABLE_TASK_CAPABILITIES),
            "selection": selection,
            "declaration_allowed": capability_setup.get("declaration_allowed", False),
            "blocking_reasons": list(capability_setup.get("blocking_reasons", [])),
        }

    async def update_capability_config(self, payload: OperatorConfigInput) -> dict[str, object]:
        selected_task_capabilities = self._normalize_selected_task_capabilities(payload.selected_task_capabilities)
        self.operator_config = self.operator_config_store.save(
            self.operator_config.model_copy(update={"selected_task_capabilities": selected_task_capabilities})
        )
        await self._refresh_post_trust_state()
        return await self.capability_config_response()

    async def capability_diagnostics(self) -> dict[str, object]:
        provider_overview = await self._provider_status_snapshot_async()
        capability_setup = self._capability_setup_summary(provider_overview)
        mqtt_health = self._mqtt_health_snapshot()
        return {
            "node_id": self.state.node_id,
            "paired_core_id": self.state.paired_core_id,
            "trust_state": self.state.trust_state,
            "operational_readiness": self.state.operational_readiness,
            "selected_task_capabilities": self.selected_task_capabilities(),
            "capability_declaration_status": self.state.capability_declaration_status,
            "capability_declared_at": self.state.capability_declared_at,
            "governance_sync_status": self.state.governance_sync_status,
            "active_governance_version": self.state.active_governance_version,
            "capability_setup": capability_setup,
            "providers": provider_overview,
            "mqtt_health": mqtt_health.model_dump(mode="json"),
        }

    async def resolved_node_capabilities(self) -> dict[str, object]:
        provider_overview = await self._provider_status_snapshot_async()
        capability_setup = self._capability_setup_summary(provider_overview)
        connected_providers = capability_setup.get("provider_selection", {}).get("enabled", [])
        selected_task_capabilities = self.selected_task_capabilities()
        return {
            "node_id": self.state.node_id,
            "trust_state": self.state.trust_state,
            "resolved_tasks": selected_task_capabilities,
            "declared_task_families": selected_task_capabilities,
            "enabled_providers": list(connected_providers) if isinstance(connected_providers, list) else [],
            "supported_providers": list(provider_overview.get("supported_providers") or []),
            "declaration_allowed": capability_setup.get("declaration_allowed", False),
            "blocking_reasons": list(capability_setup.get("blocking_reasons", [])),
        }

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

    async def status(self) -> StatusResponse:
        provider_overview = await self._provider_status_snapshot_async()
        mqtt_health = self._mqtt_health_snapshot()
        operational_mqtt_host = self.state.operational_mqtt_host or (
            self.trust_material.operational_mqtt_host if self.trust_material is not None else None
        )
        operational_mqtt_port = self.state.operational_mqtt_port or (
            self.trust_material.operational_mqtt_port if self.trust_material is not None else None
        )
        return StatusResponse(
            node_name=self.effective_node_name() or "",
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            trust_state=self.state.trust_state,
            node_id=self.state.node_id,
            paired_core_id=self.state.paired_core_id,
            mqtt_connection_status=self.mqtt_manager.status.state,
            mqtt_health=mqtt_health,
            operational_mqtt_host=operational_mqtt_host,
            operational_mqtt_port=operational_mqtt_port,
            onboarding_status=self.state.onboarding_status,
            providers=self.provider_registry.provider_ids(),
            required_inputs=self.required_inputs(),
            supported_providers=provider_overview["supported_providers"],
            enabled_providers=self.state.enabled_providers,
            provider_account_summaries=provider_overview["providers"],
            governance_sync_status=self.state.governance_sync_status,
            capability_declaration_status=self.state.capability_declaration_status,
            active_governance_version=self.state.active_governance_version,
            last_heartbeat_at=self.state.last_heartbeat_at,
            trusted_at=self.state.trusted_at,
            operational_readiness=self.state.operational_readiness,
            capability_setup=self._capability_setup_summary(provider_overview),
        )

    async def ui_bootstrap(self) -> UiBootstrapResponse:
        required_inputs = self.required_inputs()
        return UiBootstrapResponse(
            config=self.operator_config_response(),
            onboarding=self.onboarding_status(),
            status=await self.status(),
            required_inputs=required_inputs,
            can_start_onboarding=not required_inputs and self.state.trust_state != "trusted",
        )

    async def governance_status(self) -> dict[str, object]:
        return {
            "node_id": self.state.node_id,
            "paired_core_id": self.state.paired_core_id,
            "trust_state": self.state.trust_state,
            "governance_sync_status": self.state.governance_sync_status,
            "governance_synced_at": self.state.governance_synced_at,
            "active_governance_version": self.state.active_governance_version,
            "operational_readiness": self.state.operational_readiness,
        }

    async def refresh_governance(self) -> dict[str, object]:
        if self.state.trust_state != "trusted":
            raise ValueError("trusted node context is required before governance refresh")
        snapshot = await self._sync_governance()
        return {
            "node_id": self.state.node_id,
            "present": snapshot.present,
            "synced_at": snapshot.synced_at,
            "governance_version": snapshot.governance_version,
            "last_sync_result": snapshot.last_sync_result,
            "refresh_interval_s": snapshot.refresh_interval_s,
            "payload": snapshot.payload,
        }

    async def services_status(self) -> dict[str, object]:
        mqtt_health = self._mqtt_health_snapshot()
        return {
            "api": {
                "live": self.live,
                "ready": self.ready,
                "startup_error": self.startup_error,
                "port": self.config.api_port,
            },
            "ui": {
                "port": self.config.ui_port,
            },
            "mqtt": {
                "connection_status": self.mqtt_manager.status.state,
                "health_status": mqtt_health.health_status,
                "status_freshness_state": mqtt_health.status_freshness_state,
                "last_status_report_at": mqtt_health.last_status_report_at,
            },
            "providers": {
                "enabled": list(self.state.enabled_providers),
                "supported": self.provider_registry.provider_ids(),
            },
        }

    async def restart_service(self, target: str) -> dict[str, object]:
        normalized_target = (target or "").strip().lower()
        if normalized_target == "mqtt":
            self.mqtt_manager.disconnect()
            self._connect_mqtt_if_possible()
            return {"target": "mqtt", "status": "restarted", "supported": True}

        commands = {
            "backend": "./scripts/dev.sh",
            "frontend": "./scripts/ui-dev.sh",
            "node": "./scripts/start.sh",
        }
        if normalized_target in commands:
            return {
                "target": normalized_target,
                "status": "manual_required",
                "supported": False,
                "detail": "restart must be triggered by the operator outside the running API process",
                "recommended_command": commands[normalized_target],
            }

        raise ValueError(f"unsupported service target: {target}")

    async def recover_node(self) -> dict[str, object]:
        previous_state = {
            "trust_state": self.state.trust_state,
            "onboarding_status": self.state.onboarding_status,
            "node_id": self.state.node_id,
        }
        self._clear_trust_and_onboarding_state()
        self.state.last_error = None
        self.state_store.save(self.state)
        return {
            "status": "recovered",
            "supported": True,
            "recovery_action": "local_state_reset",
            "previous_state": previous_state,
            "current_state": {
                "trust_state": self.state.trust_state,
                "onboarding_status": self.state.onboarding_status,
                "node_id": self.state.node_id,
            },
        }

    async def start_gmail_connect(
        self,
        account_id: str,
        *,
        correlation_id: str | None = None,
    ) -> GmailConnectStartResponse:
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
            core_id=await self._resolve_gmail_oauth_core_id(oauth_config),
            node_id=self.state.node_id or "",
        )
        gmail_adapter = self.provider_registry.get_provider("gmail")
        if hasattr(gmail_adapter, "start_account_connect"):
            await gmail_adapter.start_account_connect(account_id)
        LOGGER.info(
            "Gmail connect flow started",
            extra={
                "event_data": {
                    "provider_id": "gmail",
                    "account_id": account_id,
                    "core_id": session.core_id,
                    "node_id": session.node_id,
                    "flow_id": session.flow_id,
                    "expires_at": session.expires_at.isoformat(),
                    "redirect_uri": session.redirect_uri,
                }
            },
        )
        return GmailConnectStartResponse(
            provider_id="gmail",
            account_id=account_id,
            connect_url=session.authorization_url or "",
            expires_at=session.expires_at,
        )

    async def handle_gmail_oauth_callback(
        self,
        *,
        state: str | None,
        code: str | None,
        error: str | None,
        error_description: str | None,
        correlation_id: str | None = None,
    ) -> GmailOAuthCallbackResponse:
        try:
            LOGGER.info(
                "Gmail oauth callback received",
                extra={"event_data": {"has_state": bool(state), "has_code": bool(code), "has_error": bool(error)}},
            )
            if error:
                message = error_description or error
                raise ValueError(f"gmail oauth failed: {message}")
            missing = [name for name, value in (("state", state), ("code", code)) if not value]
            if missing:
                raise ValueError(f"missing required query parameters: {', '.join(missing)}")

            session = self.gmail_oauth_manager.validate_callback_state(state or "")
            gmail_adapter = self.provider_registry.get_provider("gmail")
            if not hasattr(gmail_adapter, "complete_oauth_callback"):
                raise ValueError("gmail provider adapter does not support oauth completion")
            account_record = await gmail_adapter.complete_oauth_callback(
                session.account_id,
                code or "",
                redirect_uri=session.redirect_uri,
                code_verifier=session.code_verifier,
                correlation_id=correlation_id,
            )
            self.gmail_oauth_manager.consume_session(session.state)
        except (GmailProviderConfigError, AttributeError) as exc:
            LOGGER.error("Gmail oauth callback failed", extra={"event_data": {"detail": str(exc)}})
            raise ValueError(str(exc)) from exc
        except GmailTokenExchangeError as exc:
            LOGGER.error("Gmail oauth callback failed", extra={"event_data": {"detail": str(exc)}})
            raise ValueError(str(exc)) from exc
        except RuntimeError as exc:
            LOGGER.error("Gmail oauth callback failed", extra={"event_data": {"detail": str(exc)}})
            raise ValueError(str(exc)) from exc
        except ValueError as exc:
            LOGGER.error("Gmail oauth callback failed", extra={"event_data": {"detail": str(exc)}})
            raise ValueError(str(exc)) from exc

        LOGGER.info(
            "Gmail oauth callback accepted",
            extra={
                "event_data": {
                    "provider_id": "gmail",
                    "account_id": account_record.account_id,
                    "email_address": account_record.email_address,
                }
            },
        )
        await self._refresh_post_trust_state()
        token_record = self.gmail_token_store().load_token(account_record.account_id)
        return GmailOAuthCallbackResponse(
            provider_id="gmail",
            account_id=account_record.account_id,
            status=account_record.status,
            granted_scopes=(token_record.granted_scopes if token_record is not None else []),
            expires_at=(token_record.expires_at if token_record is not None else None),
        )

    def gmail_token_store(self):
        return self.provider_registry.get_provider("gmail").token_store

    async def providers_overview(self) -> dict[str, object]:
        return await self._provider_status_snapshot_async()

    async def gmail_provider_status(self) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        validation = await adapter.validate_static_config()
        accounts = await adapter.list_accounts()
        return {
            "provider_id": "gmail",
            "provider_state": await adapter.get_provider_state(),
            "enabled": adapter.get_enabled_status(),
            "configured": validation.ok,
            "validation": validation.model_dump(mode="json"),
            "accounts": [account.model_dump(mode="json") for account in accounts],
        }

    async def gmail_provider_config(self) -> dict[str, object]:
        try:
            config = self.gmail_config_store.load()
        except GmailProviderConfigError as exc:
            raise ValueError(str(exc)) from exc
        validation = self.gmail_config_store.validate(config)
        return {
            "config": config.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
        }

    async def update_gmail_provider_config(self, payload: GmailOAuthConfig) -> dict[str, object]:
        config = self.gmail_config_store.save(payload)
        validation = self.gmail_config_store.validate(config)
        await self._refresh_post_trust_state()
        return {
            "config": config.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
        }

    async def gmail_accounts_status(self) -> list[dict[str, object]]:
        adapter = self.provider_registry.get_provider("gmail")
        accounts = await adapter.list_accounts()
        return [account.model_dump(mode="json") for account in accounts]

    async def gmail_account_status(self, account_id: str) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        account = next((account for account in await adapter.list_accounts() if account.account_id == account_id), None)
        health = await adapter.get_account_health(account_id)
        mailbox_status = (
            await adapter.refresh_mailbox_status(account_id, store_unread_messages=False)
            if hasattr(adapter, "refresh_mailbox_status")
            else await adapter.get_mailbox_status(account_id) if hasattr(adapter, "get_mailbox_status") else None
        )
        return {
            "account": account.model_dump(mode="json") if account is not None else None,
            "health": health.model_dump(mode="json"),
            "mailbox_status": mailbox_status.model_dump(mode="json") if mailbox_status is not None else None,
        }

    async def gmail_status(self) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        accounts = await adapter.list_accounts()
        fetch_schedule = await adapter.fetch_schedule_state() if hasattr(adapter, "fetch_schedule_state") else None
        statuses: list[dict[str, object]] = []
        for account in accounts:
            mailbox_status = (
                await adapter.refresh_mailbox_status(account.account_id, store_unread_messages=False)
                if hasattr(adapter, "refresh_mailbox_status")
                else await adapter.get_mailbox_status(account.account_id) if hasattr(adapter, "get_mailbox_status") else None
            )
            message_summary = await adapter.message_store_summary(account.account_id) if hasattr(adapter, "message_store_summary") else None
            spamhaus_summary = await adapter.spamhaus_summary(account.account_id) if hasattr(adapter, "spamhaus_summary") else None
            quota_usage = await adapter.quota_usage_summary(account.account_id) if hasattr(adapter, "quota_usage_summary") else None
            statuses.append(
                {
                    "account": account.model_dump(mode="json"),
                    "mailbox_status": mailbox_status.model_dump(mode="json") if mailbox_status is not None else None,
                    "message_store": message_summary,
                    "spamhaus": spamhaus_summary.model_dump(mode="json") if spamhaus_summary is not None else None,
                    "quota_usage": quota_usage.model_dump(mode="json") if quota_usage is not None else None,
                }
            )
        return {
            "provider_id": "gmail",
            "provider_state": await adapter.get_provider_state(),
            "enabled": adapter.get_enabled_status(),
            "fetch_schedule": fetch_schedule.model_dump(mode="json") if fetch_schedule is not None else None,
            "accounts": statuses,
        }

    async def gmail_fetch_messages(
        self,
        window: str,
        *,
        account_id: str = "primary",
        reason: str = "manual",
        slot_key: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "fetch_messages_for_window"):
            raise ValueError("gmail fetch actions are not available")
        try:
            result = await adapter.fetch_messages_for_window(
                account_id,
                window=window,
                reason=reason,
                slot_key=slot_key,
                correlation_id=correlation_id,
            )
            if hasattr(adapter, "refresh_mailbox_status"):
                await adapter.refresh_mailbox_status(
                    account_id,
                    store_unread_messages=False,
                    correlation_id=correlation_id,
                )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return result

    async def gmail_config_validation(self) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        validation = await adapter.validate_static_config()
        return validation.model_dump(mode="json")

    async def gmail_check_spamhaus(
        self,
        *,
        account_id: str = "primary",
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "check_spamhaus_for_stored_messages"):
            raise ValueError("gmail Spamhaus actions are not available")
        try:
            return await adapter.check_spamhaus_for_stored_messages(account_id)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def gmail_training_status(self, *, account_id: str = "primary") -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        return {
            "provider_id": "gmail",
            "account_id": account_id,
            "threshold": self.config.gmail_local_classification_threshold,
            "message_store": await adapter.message_store_summary(account_id) if hasattr(adapter, "message_store_summary") else None,
        }

    async def gmail_training_manual_batch(self, *, account_id: str = "primary", limit: int = 40) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "manual_training_batch"):
            raise ValueError("gmail training actions are not available")
        try:
            return await adapter.manual_training_batch(
                account_id,
                threshold=self.config.gmail_local_classification_threshold,
                limit=limit,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def gmail_training_save_manual_classifications(
        self,
        payload: GmailManualClassificationBatchInput,
        *,
        account_id: str = "primary",
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "save_manual_classifications"):
            raise ValueError("gmail training actions are not available")
        try:
            return await adapter.save_manual_classifications(account_id, payload)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def _provider_status_snapshot_async(self) -> dict[str, object]:
        supported = self.provider_registry.list_supported_providers()
        configured: list[str] = []
        enabled: list[str] = []
        summaries: dict[str, object] = {}

        for provider_id in supported:
            adapter = self.provider_registry.get_provider(provider_id)
            validation = await adapter.validate_static_config()
            if validation.ok:
                configured.append(provider_id)
            if adapter.get_enabled_status():
                enabled.append(provider_id)
            accounts = await adapter.list_accounts()
            health = None
            if accounts:
                health = (await adapter.get_account_health(accounts[0].account_id)).model_dump(mode="json")
            summaries[provider_id] = {
                "provider_id": provider_id,
                "provider_state": await adapter.get_provider_state(),
                "enabled": adapter.get_enabled_status(),
                "configured": validation.ok,
                "account_count": len(accounts),
                "accounts": [account.model_dump(mode="json") for account in accounts],
                "health": health,
            }

        return {
            "supported_providers": supported,
            "configured_providers": configured,
            "enabled_providers": enabled,
            "providers": summaries,
        }

    async def _refresh_post_trust_state(self) -> None:
        if self.state.trust_state != "trusted" or not self.state.node_id or not self.effective_core_base_url():
            return
        provider_overview = await self._provider_status_snapshot_async()
        capability_setup = self._capability_setup_summary(provider_overview)
        connected_providers = capability_setup.get("provider_selection", {}).get("enabled", [])
        self.state.enabled_providers = list(connected_providers) if isinstance(connected_providers, list) else []
        self.state.capability_declaration_status = "pending"
        self.state.governance_sync_status = "pending"
        self.state.active_governance_version = None
        self.state_store.save(self.state)
        await self._update_operational_readiness()

    def _ensure_gmail_status_polling(self) -> None:
        if self.gmail_status_task is None or self.gmail_status_task.done():
            self.gmail_status_task = asyncio.create_task(self._gmail_status_loop())

    def _ensure_gmail_fetch_polling(self) -> None:
        if self.gmail_fetch_task is None or self.gmail_fetch_task.done():
            self.gmail_fetch_task = asyncio.create_task(self._gmail_fetch_loop())

    async def _gmail_status_loop(self) -> None:
        while True:
            with contextlib.suppress(Exception):
                await self._refresh_gmail_status()
            await asyncio.sleep(self.config.gmail_status_poll_interval_seconds)

    async def _refresh_gmail_status(self) -> None:
        gmail_adapter = self.provider_registry.get_provider("gmail")
        accounts = await gmail_adapter.list_accounts()
        for account in accounts:
            if account.status in {"connected", "token_exchanged", "degraded"}:
                await gmail_adapter.refresh_mailbox_status(account.account_id)

    async def _gmail_fetch_loop(self) -> None:
        while True:
            with contextlib.suppress(Exception):
                await self._run_due_gmail_fetches()
            await asyncio.sleep(self._seconds_until_next_minute())

    async def _run_due_gmail_fetches(self) -> None:
        gmail_adapter = self.provider_registry.get_provider("gmail")
        if not gmail_adapter.get_enabled_status():
            return
        accounts = await gmail_adapter.list_accounts()
        eligible_accounts = [account for account in accounts if account.status in {"connected", "token_exchanged", "degraded"}]
        if not eligible_accounts:
            return

        schedule_state = await gmail_adapter.fetch_schedule_state() if hasattr(gmail_adapter, "fetch_schedule_state") else None
        due_windows = self._due_gmail_fetch_windows(datetime.now().astimezone(), schedule_state)
        for account in eligible_accounts:
            for window, slot_key in due_windows:
                await self.gmail_fetch_messages(
                    window,
                    account_id=account.account_id,
                    reason="scheduled",
                    slot_key=slot_key,
                )

    def _due_gmail_fetch_windows(self, now: datetime, schedule_state) -> list[tuple[str, str]]:
        due: list[tuple[str, str]] = []
        schedule_map = {
            "yesterday": self._gmail_fetch_slot_key("yesterday", now),
            "today": self._gmail_fetch_slot_key("today", now),
            "last_hour": self._gmail_fetch_slot_key("last_hour", now),
        }
        if schedule_state is None:
            return []

        yesterday_state = getattr(schedule_state, "yesterday", None)
        if now.hour == 0 and now.minute == 1 and schedule_map["yesterday"] and getattr(yesterday_state, "last_slot_key", None) != schedule_map["yesterday"]:
            due.append(("yesterday", schedule_map["yesterday"]))

        today_state = getattr(schedule_state, "today", None)
        if now.minute == 0 and now.hour % 6 == 0 and schedule_map["today"] and getattr(today_state, "last_slot_key", None) != schedule_map["today"]:
            due.append(("today", schedule_map["today"]))

        last_hour_state = getattr(schedule_state, "last_hour", None)
        if now.minute == 0 and schedule_map["last_hour"] and getattr(last_hour_state, "last_slot_key", None) != schedule_map["last_hour"]:
            due.append(("last_hour", schedule_map["last_hour"]))

        return due

    def _gmail_fetch_slot_key(self, window: str, now: datetime) -> str | None:
        local_now = now.astimezone()
        if window == "yesterday":
            return (local_now - timedelta(days=1)).date().isoformat()
        if window == "today":
            return f"{local_now.date().isoformat()}:{local_now.hour // 6}"
        if window == "last_hour":
            slot_time = local_now.replace(minute=0, second=0, microsecond=0)
            return slot_time.isoformat()
        return None

    def _seconds_until_next_minute(self) -> float:
        now = datetime.now().astimezone()
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        return max((next_minute - now).total_seconds(), 1.0)

    async def declare_selected_capabilities(self) -> StatusResponse:
        if self.state.trust_state != "trusted" or not self.state.node_id or not self.effective_core_base_url():
            raise ValueError("trusted node context is required before declaring capabilities")
        provider_overview = await self._provider_status_snapshot_async()
        capability_setup = self._capability_setup_summary(provider_overview)
        connected_providers = capability_setup.get("provider_selection", {}).get("enabled", [])
        self.state.enabled_providers = list(connected_providers) if isinstance(connected_providers, list) else []
        if not capability_setup.get("declaration_allowed"):
            self.state.capability_declaration_status = "pending"
            self.state.governance_sync_status = "pending"
            self.state.active_governance_version = None
            self.state_store.save(self.state)
            await self._update_operational_readiness()
            raise ValueError("capability declaration is not ready yet")
        await self._declare_capabilities(provider_overview)
        await self._sync_governance()
        await self._update_operational_readiness()
        return await self.status()

    async def redeclare_capabilities(self, *, force: bool = False) -> StatusResponse:
        if force:
            self.state.capability_declaration_status = "pending"
            self.state_store.save(self.state)
        return await self.declare_selected_capabilities()

    async def rebuild_capabilities(self, *, force: bool = False) -> dict[str, object]:
        if force:
            self.state.capability_declaration_status = "pending"
            self.state.governance_sync_status = "pending"
            self.state.active_governance_version = None
            self.state_store.save(self.state)
        await self._refresh_post_trust_state()
        resolved = await self.resolved_node_capabilities()
        return {
            "status": "rebuilt",
            "force_refresh": force,
            "resolved": resolved,
        }

    async def _declare_capabilities(self, overview: dict[str, object] | None = None) -> CapabilityDeclarationResult:
        overview = overview or await self._provider_status_snapshot_async()
        enabled_providers: list[str] = []
        for provider_id, provider_summary in overview["providers"].items():
            if isinstance(provider_summary, dict) and provider_summary.get("provider_state") == "connected":
                enabled_providers.append(provider_id)
        manifest = self.capability_manifest_builder.build(
            node_id=self.state.node_id or "",
            node_type=self.config.node_type,
            node_name=self.effective_node_name() or "",
            node_software_version=self.config.node_software_version,
            declared_task_families=self.selected_task_capabilities(),
            supported_providers=list(overview["supported_providers"]),
            enabled_providers=enabled_providers,
        )
        result = await self.capability_client.declare(
            self.effective_core_base_url() or "",
            manifest,
            trust_token=(self.trust_material.node_trust_token if self.trust_material is not None else ""),
        )
        self.state.capability_declaration_status = "accepted" if result.accepted else "rejected"
        self.state.capability_declared_at = result.submitted_at
        self.state.enabled_providers = enabled_providers
        self.state_store.save(self.state)
        LOGGER.info(
            "Capability declaration submitted",
            extra={
                "event_data": {
                    "accepted": result.accepted,
                    "supported_providers": manifest.supported_providers,
                    "enabled_providers": manifest.enabled_providers,
                }
            },
        )
        return result

    async def _sync_governance(self) -> GovernanceSnapshot:
        if self.trust_material is None:
            snapshot = GovernanceSnapshot(
                node_id=self.state.node_id or "",
                present=False,
                last_sync_result="trust_material_missing",
            )
            self.state.governance_sync_status = snapshot.last_sync_result
            self.state.governance_synced_at = snapshot.synced_at
            self.state.active_governance_version = None
            self.state_store.save(self.state)
            return snapshot
        snapshot = await self.governance_client.fetch(
            self.effective_core_base_url() or "",
            self.state.node_id or "",
            trust_token=self.trust_material.node_trust_token,
            current_governance_version=self.state.active_governance_version,
        )
        self.state.governance_sync_status = snapshot.last_sync_result
        self.state.governance_synced_at = snapshot.synced_at
        self.state.active_governance_version = snapshot.governance_version
        self.state_store.save(self.state)
        LOGGER.info(
            "Governance sync result",
            extra={
                "event_data": {
                    "present": snapshot.present,
                    "last_sync_result": snapshot.last_sync_result,
                    "governance_version": snapshot.governance_version,
                }
            },
        )
        return snapshot

    async def _update_operational_readiness(self) -> None:
        gmail_state = await self.provider_registry.get_provider("gmail").get_provider_state()
        self.state.operational_readiness = self.readiness_evaluator.evaluate(
            trust_state=self.state.trust_state,
            capability_declaration_status=self.state.capability_declaration_status,
            governance_sync_status=self.state.governance_sync_status,
            gmail_provider_state=gmail_state,
        )
        self.state_store.save(self.state)
