from __future__ import annotations

import asyncio
import contextlib
import json
import re
import socket
import uuid
from email.utils import parseaddr
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
from config import AppConfig
from core.capability_client import CapabilityClient, CapabilityDeclarationResult, CapabilityManifestBuilder
from core.governance_client import GovernanceClient, GovernanceSnapshot
from core.readiness import OperationalReadinessEvaluator
from core_client import (
    CoreApiClient,
    FinalizeResponse,
    OnboardingSessionRequest,
    ServiceAuthorizeRequest,
    ServiceResolveRequest,
)
from logging_utils import get_logger
from models import (
    GmailConnectStartResponse,
    GmailOAuthCallbackResponse,
    CoreServiceAuthorizeRequestInput,
    CoreServiceResolveRequestInput,
    MqttHealthResponse,
    NodeNotificationRequest,
    NodeNotificationResult,
    NotificationContent,
    NotificationDelivery,
    NotificationEvent,
    NotificationSourceHint,
    NotificationTargets,
    OnboardingStatusResponse,
    OperatorConfig,
    OperatorConfigInput,
    OperatorConfigResponse,
    RuntimeDirectExecutionRequestInput,
    RuntimePromptExecutionRequestInput,
    RuntimeState,
    StatusResponse,
    TaskRoutingPreviewResponse,
    TaskRoutingRequestInput,
    TrustMaterial,
    UiBootstrapResponse,
)
from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.models import GmailManualClassificationBatchInput, GmailOAuthConfig, GmailSemiAutoClassificationBatchInput, GmailTrainingLabel
from providers.gmail.oauth import GmailOAuthSessionManager
from providers.gmail.token_client import GmailTokenExchangeClient, GmailTokenExchangeError
from providers.gmail.training import normalize_email_for_classifier
from mqtt import MQTTManager
from providers.registry import ProviderRegistry
from state_store import OperatorConfigStore, RuntimeStateStore, StateCorruptionError, TrustMaterialStore
from version import __version__


LOGGER = get_logger(__name__)
AI_LOGGER = get_logger("hexe.ai.runtime")
GMAIL_POLL_LOGGER = get_logger("hexe.providers.gmail.polling")
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
            on_notification_result=self._handle_notification_result,
            on_connected=self._handle_mqtt_connected,
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
        self._gmail_fetch_notification_state: str | None = None
        self._mqtt_connect_notification_count = 0

    @staticmethod
    def _default_runtime_task_state() -> dict[str, object]:
        return {
            "request_status": "idle",
            "last_step": "none",
            "detail": "No runtime task request has been started yet.",
            "preview_response": None,
            "resolve_response": None,
            "authorize_response": None,
            "registration_request_payload": None,
            "execution_request_payload": None,
            "execution_response": None,
            "usage_summary_response": None,
            "started_at": None,
            "updated_at": None,
        }

    def _runtime_task_state(self) -> dict[str, object]:
        state = dict(self._default_runtime_task_state())
        persisted = self.state.runtime_task_state if isinstance(self.state.runtime_task_state, dict) else {}
        state.update(persisted)
        return state

    def _save_runtime_task_state(self, **updates: object) -> dict[str, object]:
        state = self._runtime_task_state()
        state.update(updates)
        self.state.runtime_task_state = state
        self.state_store.save(self.state)
        return state

    @staticmethod
    def _default_gmail_last_hour_pipeline_state() -> dict[str, object]:
        return {
            "mode": "idle",
            "status": "idle",
            "detail": "No last-hour pipeline run yet.",
            "started_at": None,
            "updated_at": None,
            "last_completed_at": None,
            "stages": {
                "fetch": {"status": "idle", "detail": "Waiting", "count": 0},
                "spamhaus": {"status": "idle", "detail": "Waiting", "count": 0},
                "local_classification": {"status": "idle", "detail": "Waiting", "count": 0},
                "ai_classification": {"status": "idle", "detail": "Waiting", "count": 0},
            },
        }

    @staticmethod
    def _default_gmail_fetch_scheduler_state() -> dict[str, object]:
        return {
            "loop_enabled": False,
            "loop_active": False,
            "status": "idle",
            "detail": "Gmail fetch scheduler has not started yet.",
            "last_checked_at": None,
            "last_due_windows": [],
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error_at": None,
            "last_error": None,
        }

    def _gmail_fetch_scheduler_state(self) -> dict[str, object]:
        state = dict(self._default_gmail_fetch_scheduler_state())
        persisted = (
            self.state.gmail_fetch_scheduler_state
            if isinstance(self.state.gmail_fetch_scheduler_state, dict)
            else {}
        )
        state.update(persisted)
        state["loop_enabled"] = bool(self.config.gmail_fetch_poll_on_startup)
        state["loop_active"] = bool(self.gmail_fetch_task is not None and not self.gmail_fetch_task.done())
        return state

    def _save_gmail_fetch_scheduler_state(self, **updates: object) -> dict[str, object]:
        state = self._gmail_fetch_scheduler_state()
        state.update(updates)
        self.state.gmail_fetch_scheduler_state = state
        self.state_store.save(self.state)
        return state

    def _gmail_last_hour_pipeline_state(self) -> dict[str, object]:
        state = dict(self._default_gmail_last_hour_pipeline_state())
        persisted = (
            self.state.gmail_last_hour_pipeline_state
            if isinstance(self.state.gmail_last_hour_pipeline_state, dict)
            else {}
        )
        state.update(persisted)
        default_stages = dict(self._default_gmail_last_hour_pipeline_state()["stages"])
        persisted_stages = persisted.get("stages") if isinstance(persisted.get("stages"), dict) else {}
        default_stages.update(persisted_stages)
        state["stages"] = default_stages
        return state

    def _save_gmail_last_hour_pipeline_state(self, **updates: object) -> dict[str, object]:
        state = self._gmail_last_hour_pipeline_state()
        state.update(updates)
        self.state.gmail_last_hour_pipeline_state = state
        self.state_store.save(self.state)
        return state

    def _next_email_classify_task_id(self) -> str:
        next_counter = int(self.state.runtime_email_classify_counter or 0) + 1
        self.state.runtime_email_classify_counter = next_counter
        self.state_store.save(self.state)
        return f"email-classify-{next_counter:03d}"

    @staticmethod
    def _parse_classifier_output(output: object) -> dict[str, object] | None:
        if not isinstance(output, dict):
            return None
        if any(key in output for key in ("label", "confidence", "rationale")):
            return output
        result = output.get("result")
        if isinstance(result, dict) and any(key in result for key in ("label", "confidence", "rationale", "category", "score")):
            return result
        text = output.get("text")
        if not isinstance(text, str):
            return None
        try:
            parsed = json.loads(text)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _normalize_classifier_label(label: object) -> GmailTrainingLabel | None:
        if label is None:
            return None
        normalized = str(label).strip().lower()
        if not normalized:
            return None
        normalized = normalized.replace("-", "_").replace(" ", "_")
        alias_map = {
            "action": GmailTrainingLabel.ACTION_REQUIRED,
            "actionrequired": GmailTrainingLabel.ACTION_REQUIRED,
            "action_required": GmailTrainingLabel.ACTION_REQUIRED,
            "directhuman": GmailTrainingLabel.DIRECT_HUMAN,
            "direct_human": GmailTrainingLabel.DIRECT_HUMAN,
            "human": GmailTrainingLabel.DIRECT_HUMAN,
            "person": GmailTrainingLabel.DIRECT_HUMAN,
            "finance": GmailTrainingLabel.FINANCIAL,
            "financial": GmailTrainingLabel.FINANCIAL,
            "orders": GmailTrainingLabel.ORDER,
            "order": GmailTrainingLabel.ORDER,
            "billing": GmailTrainingLabel.INVOICE,
            "bill": GmailTrainingLabel.INVOICE,
            "receipt": GmailTrainingLabel.INVOICE,
            "invoice": GmailTrainingLabel.INVOICE,
            "shipping": GmailTrainingLabel.SHIPMENT,
            "shipment": GmailTrainingLabel.SHIPMENT,
            "delivery": GmailTrainingLabel.SHIPMENT,
            "security": GmailTrainingLabel.SECURITY,
            "system": GmailTrainingLabel.SYSTEM,
            "newsletter": GmailTrainingLabel.NEWSLETTER,
            "newsletters": GmailTrainingLabel.NEWSLETTER,
            "marketing": GmailTrainingLabel.MARKETING,
            "promo": GmailTrainingLabel.MARKETING,
            "promotion": GmailTrainingLabel.MARKETING,
            "promotions": GmailTrainingLabel.MARKETING,
            "unknown": GmailTrainingLabel.UNKNOWN,
            "other": GmailTrainingLabel.UNKNOWN,
        }
        if normalized in alias_map:
            return alias_map[normalized]
        compact = normalized.replace("_", "")
        if compact in alias_map:
            return alias_map[compact]
        try:
            return GmailTrainingLabel(normalized)
        except Exception:
            return None

    @staticmethod
    def _normalize_classifier_confidence(confidence: object) -> float | None:
        if confidence is None:
            return None
        if isinstance(confidence, str):
            normalized = confidence.strip().rstrip("%")
            if not normalized:
                return None
            try:
                value = float(normalized)
            except Exception:
                return None
            if "%" in confidence or value > 1:
                value = value / 100.0
        else:
            try:
                value = float(confidence)
            except Exception:
                return None
            if value > 1:
                value = value / 100.0
        return max(0.0, min(1.0, value))

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

    def _handle_notification_result(self, result: NodeNotificationResult) -> None:
        if result.accepted:
            return
        LOGGER.warning(
            "Core rejected user notification request",
            extra={
                "event_data": {
                    "request_id": result.request_id,
                    "node_id": result.node_id,
                    "error": result.error,
                }
            },
        )

    def _handle_mqtt_connected(self) -> None:
        self._mqtt_connect_notification_count += 1
        generation = self._mqtt_connect_notification_count
        label = "Hexe Email online" if generation == 1 else "Hexe Email back online"
        message = (
            "The email node finished startup and is connected to Core."
            if generation == 1
            else "The email node reconnected to Core and is back online."
        )
        self.send_user_notification(
            title=label,
            message=message,
            severity="success",
            urgency="notification",
            dedupe_key=f"node-online-{generation}",
            event_type="node_online" if generation == 1 else "node_reconnected",
            summary="Email node connected to Core",
            source_component="mqtt_runtime",
            data={"connection_generation": generation, "connection_state": "connected"},
        )

    def _invalidate_capability_state(self) -> None:
        self.state.capability_declaration_status = "pending"
        self.state.governance_sync_status = "pending"
        self.state.active_governance_version = None
        self.state_store.save(self.state)

    def send_user_notification(
        self,
        *,
        title: str,
        message: str,
        severity: str,
        urgency: str,
        dedupe_key: str,
        event_type: str,
        summary: str,
        source_component: str,
        data: dict[str, object] | None = None,
    ) -> bool:
        if self.state.trust_state != "trusted" or not self.state.node_id:
            return False
        if self.mqtt_manager.status.state != "connected":
            LOGGER.info(
                "Skipping user notification because MQTT is not connected",
                extra={"event_data": {"dedupe_key": dedupe_key, "connection_state": self.mqtt_manager.status.state}},
            )
            return False

        request = NodeNotificationRequest(
            request_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC),
            node_id=self.state.node_id,
            kind="event",
            targets=NotificationTargets(
                broadcast=True,
                external=["ha"],
            ),
            delivery=NotificationDelivery(
                severity=severity,
                priority="high" if severity in {"warning", "error", "critical"} else "normal",
                urgency=urgency,
                dedupe_key=dedupe_key,
                channels=["event", "external"],
                ttl_seconds=3600,
            ),
            source=NotificationSourceHint(
                component=source_component,
                label=self.effective_node_name() or self.config.node_type,
                metadata={"node_type": self.config.node_type},
            ),
            content=NotificationContent(
                title=title,
                message=message,
            ),
            event=NotificationEvent(
                event_type=event_type,
                summary=summary,
                attributes={"component": source_component},
            ),
            data=data or {},
        )
        return self.mqtt_manager.publish_notification_request(request)

    def _set_gmail_fetch_notification_state(self, next_state: str, detail: str) -> None:
        previous = self._gmail_fetch_notification_state
        self._gmail_fetch_notification_state = next_state

        if next_state == previous:
            return

        if next_state == "warning":
            self.send_user_notification(
                title="Hexe Email warning",
                message=detail,
                severity="warning",
                urgency="actions_needed",
                dedupe_key="gmail-fetch-warning",
                event_type="gmail_fetch_warning",
                summary="Gmail fetch scheduler needs attention",
                source_component="gmail_fetch_scheduler",
                data={"status": "warning"},
            )
            return

        if next_state == "error":
            self.send_user_notification(
                title="Hexe Email error",
                message=detail,
                severity="error",
                urgency="urgent",
                dedupe_key="gmail-fetch-error",
                event_type="gmail_fetch_error",
                summary="Gmail fetch scheduler hit an error",
                source_component="gmail_fetch_scheduler",
                data={"status": "error"},
            )
            return

        if next_state == "healthy" and previous in {"warning", "error"}:
            self.send_user_notification(
                title="Hexe Email back online",
                message="Gmail fetch scheduling recovered and is running again.",
                severity="success",
                urgency="notification",
                dedupe_key="gmail-fetch-recovered",
                event_type="gmail_fetch_recovered",
                summary="Gmail fetch scheduler recovered",
                source_component="gmail_fetch_scheduler",
                data={"status": "healthy", "recovered_from": previous},
            )

    def send_email_classification_notification(
        self,
        *,
        classification_label: GmailTrainingLabel,
        sender: str | None,
        subject: str | None,
        confidence: float | None,
        sender_reputation: dict[str, object] | None,
        message_id: str,
        source_component: str,
    ) -> bool:
        notification_specs = {
            GmailTrainingLabel.ACTION_REQUIRED: {
                "title": "Action Required email",
                "severity": "warning",
                "urgency": "actions_needed",
                "event_type": "gmail_action_required_email",
                "summary": "New action-required email classified",
            },
            GmailTrainingLabel.ORDER: {
                "title": "Order email",
                "severity": "info",
                "urgency": "notification",
                "event_type": "gmail_order_email",
                "summary": "New order email classified",
            },
        }
        spec = notification_specs.get(classification_label)
        if spec is None:
            return False

        confidence_text = f"{confidence:.2f}" if confidence is not None else "unknown"
        sender_text = (sender or "Unknown sender").strip() or "Unknown sender"
        subject_text = (subject or "(no subject)").strip() or "(no subject)"
        sender_reputation_text = self._sender_reputation_notification_text(sender_reputation)
        message_lines = [
            f"From: {sender_text}",
            f"Subject: {subject_text}",
            f"Confidence: {confidence_text}",
        ]
        if sender_reputation_text:
            message_lines.append(sender_reputation_text)
        return self.send_user_notification(
            title=spec["title"],
            message="\n".join(message_lines),
            severity=spec["severity"],
            urgency=spec["urgency"],
            dedupe_key=f"gmail-classification-{classification_label.value}-{message_id}",
            event_type=spec["event_type"],
            summary=spec["summary"],
            source_component=source_component,
            data={
                "message_id": message_id,
                "classification_label": classification_label.value,
                "sender": sender,
                "subject": subject,
                "confidence": confidence,
                "sender_reputation": sender_reputation,
            },
        )

    def _notify_for_new_email_classification(
        self,
        *,
        account_id: str,
        message_id: str,
        classification_label: GmailTrainingLabel,
        confidence: float | None,
        source_component: str,
    ) -> bool:
        adapter = self.provider_registry.get_provider("gmail")
        if not adapter.message_store.get_message(account_id, message_id):
            return False
        if adapter.message_store.has_notification_label(account_id, message_id, classification_label.value):
            return False
        message = adapter.message_store.get_message(account_id, message_id)
        if message is None:
            return False
        sender_reputation = self._sender_reputation_context(account_id, sender=message.sender)
        sent = self.send_email_classification_notification(
            classification_label=classification_label,
            sender=message.sender,
            subject=message.subject,
            confidence=confidence,
            sender_reputation=sender_reputation,
            message_id=message_id,
            source_component=source_component,
        )
        if sent:
            adapter.message_store.mark_notification_label_sent(account_id, message_id, classification_label.value)
        return sent

    def _sender_reputation_context(self, account_id: str, *, sender: str | None) -> dict[str, object] | None:
        adapter = self.provider_registry.get_provider("gmail")
        _, sender_email = parseaddr(sender or "")
        sender_email = sender_email.strip().lower()
        sender_domain = sender_email.split("@", 1)[1].strip().lower() if "@" in sender_email else ""
        email_record = (
            adapter.message_store.get_sender_reputation(account_id, entity_type="email", sender_value=sender_email)
            if sender_email
            else None
        )
        domain_record = (
            adapter.message_store.get_sender_reputation(account_id, entity_type="domain", sender_value=sender_domain)
            if sender_domain
            else None
        )
        preferred = email_record or domain_record
        if preferred is None:
            return None
        return {
            "sender_email": sender_email or None,
            "sender_domain": sender_domain or None,
            "preferred": preferred.model_dump(mode="json"),
            "email": email_record.model_dump(mode="json") if email_record is not None else None,
            "domain": domain_record.model_dump(mode="json") if domain_record is not None else None,
        }

    def _sender_reputation_notification_text(self, sender_reputation: dict[str, object] | None) -> str | None:
        if not isinstance(sender_reputation, dict):
            return None
        preferred = sender_reputation.get("preferred")
        if not isinstance(preferred, dict):
            return None
        state = preferred.get("reputation_state") or "neutral"
        rating = preferred.get("rating")
        sender_value = preferred.get("sender_value") or sender_reputation.get("sender_domain") or sender_reputation.get("sender_email")
        rating_text = f"{float(rating):.2f}" if isinstance(rating, (int, float)) else "unknown"
        return f"Sender reputation: {state} ({rating_text}) [{sender_value}]"

    def _build_ai_classifier_input_text(
        self,
        message,
        *,
        my_addresses: list[str] | None,
        sender_reputation: dict[str, object] | None,
    ) -> str:
        normalized_text = normalize_email_for_classifier(message, my_addresses=my_addresses)
        if not isinstance(sender_reputation, dict):
            return normalized_text
        preferred = sender_reputation.get("preferred")
        if not isinstance(preferred, dict):
            return normalized_text
        reputation_lines = [
            f"sender_reputation_state: {preferred.get('reputation_state') or 'neutral'}",
            f"sender_reputation_rating: {preferred.get('rating') if preferred.get('rating') is not None else 'unknown'}",
            f"sender_reputation_messages: {preferred.get('inputs', {}).get('message_count', 0) if isinstance(preferred.get('inputs'), dict) else 0}",
            f"sender_reputation_spamhaus_listed: {preferred.get('inputs', {}).get('spamhaus_listed_count', 0) if isinstance(preferred.get('inputs'), dict) else 0}",
        ]
        return f"{normalized_text}\n" + "\n".join(reputation_lines)

    def _send_runtime_batch_classification_summary_notification(
        self,
        *,
        batch_size: int,
        local_classified: int,
        ai_completed: int,
        ai_attempted: int = 0,
    ) -> bool:
        return self.send_user_notification(
            title="Manual batch classification completed",
            message=(
                f"Batch size: {batch_size}\n"
                f"Successfully classified locally: {local_classified}\n"
                f"Classified by AI node: {ai_completed}\n"
                f"AI attempted: {ai_attempted}"
            ),
            severity="info",
            urgency="notification",
            dedupe_key=f"runtime-batch-classification-{datetime.now(UTC).isoformat()}",
            event_type="runtime_batch_classification_completed",
            summary="Manual batch classification completed",
            source_component="runtime_batch_classification",
            data={
                "batch_size": batch_size,
                "local_classified": local_classified,
                "ai_completed": ai_completed,
                "ai_attempted": ai_attempted,
            },
        )

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
        if self.state.trust_state == "trusted":
            self._invalidate_capability_state()
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

    async def task_routing_preview(self, payload: TaskRoutingRequestInput) -> TaskRoutingPreviewResponse:
        selected_task_capabilities = self.selected_task_capabilities()
        requested_node_type = (payload.requested_node_type or "").strip() or None
        requested_provider = (payload.requested_provider or "").strip() or None
        local_node_type = self.config.node_type
        capability_declared = self.state.capability_declaration_status == "accepted"
        local_family_match = payload.task_family in selected_task_capabilities
        node_type_match = requested_node_type in {None, local_node_type}
        local_node_can_execute = local_family_match and node_type_match
        should_delegate_to_core = requested_node_type is not None and requested_node_type != local_node_type

        if should_delegate_to_core:
            detail = (
                f"Task requests for node type {requested_node_type} should be sent to Core for routing; "
                f"this node is {local_node_type}."
            )
        elif not local_family_match:
            detail = "This node has not selected that task family locally, so Core routing is recommended."
            should_delegate_to_core = True
        elif not capability_declared:
            detail = "This node can describe the task intent locally, but Core should only route after capability declaration is accepted."
        else:
            detail = "This node can accept this task family locally under the current node-type selection."

        return TaskRoutingPreviewResponse(
            task_family=payload.task_family,
            requested_node_type=requested_node_type,
            requested_provider=requested_provider,
            local_node_type=local_node_type,
            local_selected_task_capabilities=selected_task_capabilities,
            local_node_can_execute=local_node_can_execute,
            should_delegate_to_core=should_delegate_to_core,
            capability_declared=capability_declared,
            detail=detail,
        )

    async def core_service_resolve(
        self,
        payload: CoreServiceResolveRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        if self.state.trust_state != "trusted" or not self.state.node_id or not self.effective_core_base_url():
            raise ValueError("trusted node context is required before resolving a Core service")
        if self.trust_material is None:
            raise ValueError("trust material is not available")
        try:
            response = await self.core_client.resolve_service(
                self.effective_core_base_url() or "",
            ServiceResolveRequest(
                node_id=self.state.node_id,
                task_family=payload.task_family,
                type=payload.type,
                task_context=payload.task_context,
                preferred_provider=payload.preferred_provider,
            ),
                trust_token=self.trust_material.node_trust_token,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        payload = response.model_dump(mode="json")
        now = datetime.now(UTC).isoformat()
        current = self._runtime_task_state()
        self._save_runtime_task_state(
            request_status="resolved",
            last_step="resolve",
            detail=f"Resolved {payload.get('selected_service_id') or payload.get('service_id') or 'service'} for {payload.get('task_family') or payload.task_family}.",
            preview_response=current.get("preview_response"),
            resolve_response=payload,
            authorize_response=current.get("authorize_response"),
            execution_response=current.get("execution_response"),
            usage_summary_response=current.get("usage_summary_response"),
            started_at=current.get("started_at") or now,
            updated_at=now,
        )
        return payload

    async def core_service_authorize(
        self,
        payload: CoreServiceAuthorizeRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        if self.state.trust_state != "trusted" or not self.state.node_id or not self.effective_core_base_url():
            raise ValueError("trusted node context is required before authorizing a Core service")
        if self.trust_material is None:
            raise ValueError("trust material is not available")
        try:
            response = await self.core_client.authorize_service(
                self.effective_core_base_url() or "",
                ServiceAuthorizeRequest(
                    node_id=self.state.node_id,
                    task_family=payload.task_family,
                    type=payload.type,
                    task_context=payload.task_context,
                    service_id=payload.service_id,
                    provider=payload.provider,
                    model_id=payload.model_id,
                ),
                trust_token=self.trust_material.node_trust_token,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        payload = response.model_dump(mode="json")
        now = datetime.now(UTC).isoformat()
        current = self._runtime_task_state()
        authorized = bool(payload.get("authorized") is True or payload.get("token") or payload.get("grant_id"))
        self._save_runtime_task_state(
            request_status="authorized" if authorized else "rejected",
            last_step="authorize",
            detail=(
                f"Authorized {payload.get('service_id') or 'service'} with {payload.get('provider') or ''}"
                if authorized
                else "Core did not authorize the requested service."
            ),
            preview_response=current.get("preview_response"),
            resolve_response=current.get("resolve_response"),
            authorize_response=payload,
            execution_response=current.get("execution_response"),
            usage_summary_response=current.get("usage_summary_response"),
            started_at=current.get("started_at") or now,
            updated_at=now,
        )
        return payload

    async def runtime_execute_authorized_task(
        self,
        payload: RuntimeDirectExecutionRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        target_base_url = str(payload.target_api_base_url or "http://127.0.0.1:9002").strip().rstrip("/")
        normalized_target_base_url = target_base_url[:-4] if target_base_url.endswith("/api") else target_base_url
        registration_id = f"runtime-{uuid.uuid4().hex}"
        request_body = self._email_classifier_prompt_registration_payload()

        try:
            registration_payload = await self._register_email_classifier_prompt(normalized_target_base_url)
        except Exception as exc:
            response_payload: dict[str, object] | None = None
            message = str(exc)
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                try:
                    response_body = exc.response.json()
                except Exception:
                    response_body = exc.response.text
                response_payload = {
                    "status_code": exc.response.status_code,
                    "body": response_body,
                }
                message = f"{message}: {response_body}"
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            self._save_runtime_task_state(
                request_status="failed",
                last_step="register",
                detail=message,
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=request_body,
                execution_response=response_payload,
                usage_summary_response=None,
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
            error = ValueError(message)
            error.detail = {
                "message": message,
                "request_payload": request_body,
                "response_payload": response_payload,
            }
            raise error from exc

        result = {
            "ok": True,
            "task_id": registration_id,
            "trace_id": correlation_id or registration_id,
            "target_api_base_url": normalized_target_base_url,
            "request_payload": request_body,
            "registration": registration_payload,
            "usage_summary": None,
        }
        now = datetime.now(UTC).isoformat()
        current = self._runtime_task_state()
        self._save_runtime_task_state(
            request_status="registered",
            last_step="register",
            detail="Registered prompt.email.classifier on the AI node prompt service.",
            preview_response=current.get("preview_response"),
            resolve_response=current.get("resolve_response"),
            authorize_response=current.get("authorize_response"),
            registration_request_payload=result["request_payload"],
            execution_response=result["registration"],
            usage_summary_response=None,
            started_at=current.get("started_at") or now,
            updated_at=now,
        )
        return result

    def _email_classifier_prompt_registration_payload(self) -> dict[str, object]:
        return {
            "prompt_id": "prompt.email.classifier",
            "service_id": "node-email",
            "task_family": "task.classification",
            "prompt_name": "Email Classifier",
            "owner_service": "node-email",
            "privacy_class": "internal",
            "status": "active",
            "execution_policy": {
                "allow_direct_execution": True,
                "allow_version_pinning": True,
            },
            "provider_preferences": {
                "preferred_providers": ["openai"],
            },
            "constraints": {
                "max_timeout_s": 60,
                "structured_output_required": True,
            },
            "metadata": {
                "purpose": "classify incoming email into email-node categories",
                "labels": [
                    "action_required",
                    "direct_human",
                    "financial",
                    "order",
                    "invoice",
                    "shipment",
                    "security",
                    "system",
                    "newsletter",
                    "marketing",
                    "unknown",
                ],
            },
            "definition": {
                "system_prompt": (
                    "You are an email classification service for the Email Node. "
                    "Classify the email into exactly one of the following labels: "
                    "action_required, direct_human, financial, order, invoice, shipment, "
                    "security, system, newsletter, marketing, unknown. Use the normalized "
                    "email input as the source of truth. Be strict and prefer the most "
                    "specific correct label. Classification guidance: action_required = "
                    "direct action needed by the recipient; direct_human = person-to-person "
                    "or community/personal message not primarily automated marketing; "
                    "financial = banking, account balance, payments, loans, statements, "
                    "financial activity unless a more specific invoice label clearly applies; "
                    "order = order placed, order confirmation, purchase confirmation; "
                    "invoice = bill, invoice, statement, receipt, charge record, payment "
                    "receipt; shipment = shipped, out for delivery, delivered, pickup ready, "
                    "travel/delivery status; security = fraud alerts, blocked activity, "
                    "password resets, suspicious sign-in, account protection, website/app "
                    "blocked, security monitoring; system = operational notices, "
                    "product/account updates, app/account state changes, reminders, "
                    "claims/repair status, task updates, service notifications; newsletter = "
                    "digest, roundup, editorial updates, forum/news/community/event "
                    "newsletters; marketing = promotions, discounts, offers, sales, product "
                    "pushes, invitations to buy/apply/upgrade; unknown = only when the "
                    "message does not fit any label with reasonable confidence. If multiple "
                    "labels seem possible, choose the most specific one. Return JSON only "
                    "with keys: label, confidence, rationale. confidence must be a number "
                    "from 0.0 to 1.0. rationale must be short, one sentence max."
                ),
                "template_variables": ["normalized_text"],
                "default_inputs": {},
            },
            "version": "v1",
        }

    async def _register_email_classifier_prompt(self, target_api_base_url: str) -> dict[str, object]:
        request_body = self._email_classifier_prompt_registration_payload()
        try:
            AI_LOGGER.info(
                "Registering email classifier prompt with AI node",
                extra={"event_data": {"target_api_base_url": target_api_base_url}},
            )
            async with httpx.AsyncClient(
                base_url=target_api_base_url,
                timeout=self.core_client.timeout,
                transport=self.core_client.transport,
            ) as client:
                registration_response = await client.post("/api/prompts/services", json=request_body)
                registration_response.raise_for_status()
                AI_LOGGER.info(
                    "AI prompt registration completed",
                    extra={"event_data": {"status_code": registration_response.status_code}},
                )
                return registration_response.json()
        except Exception as exc:
            AI_LOGGER.error(
                "AI prompt registration failed",
                extra={"event_data": {"target_api_base_url": target_api_base_url, "detail": str(exc)}},
            )
            raise ValueError(str(exc)) from exc

    async def runtime_execute_email_classifier(
        self,
        payload: RuntimePromptExecutionRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        account_id = "primary"
        newest_unknown_message = adapter.message_store.get_newest_unknown_message(account_id)
        if newest_unknown_message is None:
            raise ValueError("no newest unknown Gmail message is available")
        return await self._execute_email_classifier_for_message(
            account_id=account_id,
            message=newest_unknown_message,
            target_api_base_url=payload.target_api_base_url,
            correlation_id=correlation_id,
            persist_runtime_state=True,
        )

    async def runtime_execute_email_classifier_batch(
        self,
        payload: RuntimePromptExecutionRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        account_id = "primary"
        batch_target_api_base_url = payload.target_api_base_url
        started_at = datetime.now(UTC).isoformat()
        current = self._runtime_task_state()
        self._save_runtime_task_state(
            request_status="running",
            last_step="execute_batch",
            detail="Preparing runtime batch classification for 100 Gmail messages...",
            preview_response=current.get("preview_response"),
            resolve_response=current.get("resolve_response"),
            authorize_response=current.get("authorize_response"),
            registration_request_payload=current.get("registration_request_payload"),
            execution_request_payload=None,
            execution_response={
                "mode": "batch",
                "stage": "local",
                "batch_size": 0,
                "local_processed": 0,
                "ai_total": 0,
                "ai_completed": 0,
                "progress_percent": 0,
                "last_message_id": None,
                "completed_messages": [],
            },
            usage_summary_response=None,
            started_at=current.get("started_at") or started_at,
            updated_at=started_at,
        )

        candidates = adapter.message_store.list_oldest_training_candidates(
            account_id,
            limit=100,
            threshold=self.config.gmail_local_classification_threshold,
        )
        if not candidates:
            now = datetime.now(UTC).isoformat()
            result = {
                "ok": True,
                "batch_size": 0,
                "local_processed": 0,
                "ai_total": 0,
                "ai_completed": 0,
                "ai_results": [],
            }
            self._save_runtime_task_state(
                request_status="executed",
                last_step="execute_batch",
                detail="No Gmail messages were available for runtime batch classification.",
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=current.get("registration_request_payload"),
                execution_request_payload=None,
                execution_response=result,
                usage_summary_response=None,
                started_at=current.get("started_at") or started_at,
                updated_at=now,
            )
            self._send_runtime_batch_classification_summary_notification(
                batch_size=0,
                local_classified=0,
                ai_completed=0,
                ai_attempted=0,
            )
            return result

        local_processed, ai_candidates = self._classify_candidates_locally(account_id=account_id, candidates=candidates)
        local_classified = max(local_processed - len(ai_candidates), 0)
        if local_processed > 0 and hasattr(adapter, "refresh_sender_reputations"):
            await adapter.refresh_sender_reputations(account_id)
        ai_total = len(ai_candidates)
        progress_payload = {
            "mode": "batch",
            "stage": "ai" if ai_total > 0 else "completed",
            "batch_size": len(candidates),
            "local_processed": local_processed,
            "local_classified": local_classified,
            "ai_total": ai_total,
            "ai_completed": 0,
            "ai_attempted": 0,
            "progress_percent": 0 if ai_total > 0 else 100,
            "last_message_id": None,
            "completed_messages": [],
        }
        self._save_runtime_task_state(
            request_status="running" if ai_total > 0 else "executed",
            last_step="execute_batch",
            detail=(
                f"Local classification successfully classified {local_classified} emails. Sending {ai_total} unknown emails to the AI node..."
                if ai_total > 0
                else f"Local classification successfully classified {local_classified} emails. No unknown emails needed AI classification."
            ),
            preview_response=current.get("preview_response"),
            resolve_response=current.get("resolve_response"),
            authorize_response=current.get("authorize_response"),
            registration_request_payload=current.get("registration_request_payload"),
            execution_request_payload=None,
            execution_response=progress_payload,
            usage_summary_response=None,
            started_at=current.get("started_at") or started_at,
            updated_at=datetime.now(UTC).isoformat(),
        )

        async def save_batch_progress(result: dict[str, object], attempted: int, succeeded: int) -> None:
            LOGGER.info(
                "Runtime batch AI response received",
                extra={
                    "event_data": {
                        "attempted": attempted,
                        "ai_total": ai_total,
                        "message_id": result.get("message_id"),
                        "classification_applied": bool(result.get("classification_applied")),
                        "parsed_output": result.get("parsed_output"),
                        "execution": result.get("execution"),
                    }
                },
            )
            progress_percent = int((attempted / ai_total) * 100) if ai_total > 0 else 100
            self._save_runtime_task_state(
                request_status="running" if attempted < ai_total else "executed",
                last_step="execute_batch",
                detail=(
                    f"AI classification progress: attempted {attempted}/{ai_total}, applied {succeeded} classifications."
                    if ai_total > 0
                    else "No unknown emails needed AI classification."
                ),
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=current.get("registration_request_payload"),
                execution_request_payload=result["request_payload"],
                execution_response={
                    "mode": "batch",
                    "stage": "ai" if attempted < ai_total else "completed",
                    "batch_size": len(candidates),
                    "local_processed": local_processed,
                    "local_classified": local_classified,
                    "ai_total": ai_total,
                    "ai_completed": succeeded,
                    "ai_attempted": attempted,
                    "progress_percent": progress_percent,
                    "last_message_id": result["message_id"],
                    "completed_messages": [],
                    "last_execution": result["execution"],
                },
                usage_summary_response=None,
                started_at=current.get("started_at") or started_at,
                updated_at=datetime.now(UTC).isoformat(),
            )

        raw_ai_results, _ = await self._execute_email_classifier_for_messages(
            account_id=account_id,
            messages=ai_candidates,
            target_api_base_url=batch_target_api_base_url,
            correlation_id=correlation_id,
            on_result=save_batch_progress,
        )
        ai_results: list[dict[str, object]] = []
        ai_succeeded = 0
        for index, result in enumerate(raw_ai_results, start=1):
            if result.get("classification_applied"):
                ai_succeeded += 1
            ai_results.append(
                {
                    "message_id": result["message_id"],
                    "task_id": result["task_id"],
                    "classification_applied": bool(result.get("classification_applied")),
                    "execution": result["execution"],
                    "request_payload": result["request_payload"],
                }
            )
        final_result = {
            "ok": True,
            "batch_size": len(candidates),
            "local_processed": local_processed,
            "local_classified": local_classified,
            "ai_total": ai_total,
            "ai_attempted": len(ai_results),
            "ai_completed": ai_succeeded,
            "ai_failed": len(ai_results) - ai_succeeded,
            "ai_results": ai_results,
        }
        self._save_runtime_task_state(
            request_status="executed",
            last_step="execute_batch",
            detail=(
                f"Runtime batch classification completed. Local classified {local_classified} emails successfully, AI attempted {len(ai_results)} unknown emails, and classified {ai_succeeded} emails."
            ),
            preview_response=current.get("preview_response"),
            resolve_response=current.get("resolve_response"),
            authorize_response=current.get("authorize_response"),
            registration_request_payload=current.get("registration_request_payload"),
            execution_request_payload=ai_results[-1]["request_payload"] if ai_results else None,
            execution_response=final_result,
            usage_summary_response=None,
            started_at=current.get("started_at") or started_at,
            updated_at=datetime.now(UTC).isoformat(),
        )
        self._send_runtime_batch_classification_summary_notification(
            batch_size=len(candidates),
            local_classified=local_classified,
            ai_completed=ai_succeeded,
            ai_attempted=len(ai_results),
        )
        return final_result

    def _classify_candidates_locally(self, *, account_id: str, candidates: list) -> tuple[int, list]:
        adapter = self.provider_registry.get_provider("gmail")
        model_status = adapter.training_model_store.status()
        if not candidates:
            return 0, []
        if not bool(model_status.get("trained")):
            return 0, list(candidates)

        account_record = adapter.account_store.load_account(account_id)
        my_addresses = [account_record.email_address] if account_record is not None and account_record.email_address else []
        texts = [normalize_email_for_classifier(message, my_addresses=my_addresses) for message in candidates]
        predictions = adapter.training_model_store.predict(texts, threshold=self.config.gmail_local_classification_threshold)

        local_processed = 0
        ai_candidates = []
        for message, prediction in zip(candidates, predictions, strict=False):
            predicted_label = GmailTrainingLabel(str(prediction["predicted_label"]))
            predicted_confidence = float(prediction["predicted_confidence"])
            adapter.message_store.update_local_classification(
                account_id,
                message.message_id,
                label=predicted_label,
                confidence=predicted_confidence,
                manual_classification=False,
            )
            self._notify_for_new_email_classification(
                account_id=account_id,
                message_id=message.message_id,
                classification_label=predicted_label,
                confidence=predicted_confidence,
                source_component="gmail_local_classification",
            )
            local_processed += 1
            if predicted_label == GmailTrainingLabel.UNKNOWN:
                ai_candidates.append(message)
        return local_processed, ai_candidates

    async def _execute_email_classifier_for_message(
        self,
        *,
        account_id: str,
        message,
        target_api_base_url: str | None,
        correlation_id: str | None,
        persist_runtime_state: bool,
    ) -> dict[str, object]:
        target_base_url = str(target_api_base_url or "http://127.0.0.1:9002").strip().rstrip("/")
        normalized_target_base_url = target_base_url[:-4] if target_base_url.endswith("/api") else target_base_url
        adapter = self.provider_registry.get_provider("gmail")
        account_record = adapter.account_store.load_account(account_id)
        my_addresses = [account_record.email_address] if account_record is not None and account_record.email_address else []
        sender_reputation = self._sender_reputation_context(account_id, sender=message.sender)
        normalized_text = self._build_ai_classifier_input_text(
            message,
            my_addresses=my_addresses,
            sender_reputation=sender_reputation,
        )

        task_id = self._next_email_classify_task_id()
        trace_id = correlation_id or f"trace-email-{uuid.uuid4().hex}"
        request_body = {
            "task_id": task_id,
            "prompt_id": "prompt.email.classifier",
            "prompt_version": "v1",
            "task_family": "task.classification",
            "requested_by": "node-email",
            "service_id": "node-email",
            "customer_id": "local-user",
            "trace_id": trace_id,
            "inputs": {
                "text": normalized_text,
                "json_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {
                            "type": "string",
                            "enum": [
                                "action_required",
                                "direct_human",
                                "financial",
                                "order",
                                "invoice",
                                "shipment",
                                "security",
                                "system",
                                "newsletter",
                                "marketing",
                                "unknown",
                            ],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "rationale": {
                            "type": "string",
                        },
                    },
                    "required": ["label", "confidence", "rationale"],
                },
            },
            "timeout_s": 60,
        }

        try:
            AI_LOGGER.info(
                "Executing email classifier against AI node",
                extra={
                    "event_data": {
                        "target_api_base_url": normalized_target_base_url,
                        "message_id": message.message_id,
                        "task_id": task_id,
                    }
                },
            )
            async with httpx.AsyncClient(
                base_url=normalized_target_base_url,
                timeout=self.core_client.timeout,
                transport=self.core_client.transport,
            ) as client:
                execution_response = await client.post("/api/execution/direct", json=request_body)
                execution_response.raise_for_status()
                execution_payload = execution_response.json()
        except Exception as exc:
            AI_LOGGER.error(
                "AI classifier execution failed",
                extra={
                    "event_data": {
                        "target_api_base_url": normalized_target_base_url,
                        "message_id": message.message_id,
                        "task_id": task_id,
                        "detail": str(exc),
                    }
                },
            )
            raise ValueError(str(exc)) from exc

        classifier_output = self._parse_classifier_output(
            execution_payload.get("output") if isinstance(execution_payload, dict) else None
        )
        classification_applied = False
        parsed_classifier_output = None
        if classifier_output is not None:
            label = classifier_output.get("label", classifier_output.get("category"))
            confidence = classifier_output.get("confidence", classifier_output.get("score"))
            parsed_label = self._normalize_classifier_label(label)
            parsed_confidence = self._normalize_classifier_confidence(confidence)
            parsed_classifier_output = {
                "raw": classifier_output,
                "normalized_label": parsed_label.value if parsed_label is not None else None,
                "normalized_confidence": parsed_confidence,
            }
            if parsed_label is not None and parsed_confidence is not None:
                adapter.message_store.update_local_classification(
                    account_id,
                    message.message_id,
                    label=parsed_label,
                    confidence=parsed_confidence,
                    manual_classification=False,
                )
                self._notify_for_new_email_classification(
                    account_id=account_id,
                    message_id=message.message_id,
                    classification_label=parsed_label,
                    confidence=parsed_confidence,
                    source_component="gmail_ai_classification",
                )
                classification_applied = True

        result = {
            "ok": True,
            "task_id": task_id,
            "trace_id": trace_id,
            "target_api_base_url": normalized_target_base_url,
            "message_id": message.message_id,
            "classification_applied": classification_applied,
            "request_payload": request_body,
            "execution": execution_payload,
            "parsed_output": parsed_classifier_output,
            "sender_reputation": sender_reputation,
        }
        AI_LOGGER.info(
            "AI classifier execution completed",
            extra={
                "event_data": {
                    "target_api_base_url": normalized_target_base_url,
                    "message_id": message.message_id,
                    "task_id": task_id,
                    "classification_applied": classification_applied,
                    "normalized_label": (
                        parsed_classifier_output.get("normalized_label")
                        if isinstance(parsed_classifier_output, dict)
                        else None
                    ),
                }
            },
        )
        if persist_runtime_state:
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            self._save_runtime_task_state(
                request_status="executed",
                last_step="execute",
                detail=f"Executed prompt.email.classifier for newest unknown email {message.message_id} on the AI node.",
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=current.get("registration_request_payload"),
                execution_request_payload=result["request_payload"],
                execution_response=result["execution"],
                usage_summary_response=None,
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
        return result

    async def _execute_email_classifier_for_messages(
        self,
        *,
        account_id: str,
        messages: list,
        target_api_base_url: str | None,
        correlation_id: str | None,
        on_result: Callable[[dict[str, object], int, int], Awaitable[None]] | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        results: list[dict[str, object]] = []
        succeeded = 0
        for message in messages:
            result = await self._execute_email_classifier_for_message(
                account_id=account_id,
                message=message,
                target_api_base_url=target_api_base_url,
                correlation_id=correlation_id,
                persist_runtime_state=False,
            )
            if result.get("classification_applied"):
                succeeded += 1
            results.append(result)
            if on_result is not None:
                await on_result(result, len(results), succeeded)
        if succeeded > 0:
            adapter = self.provider_registry.get_provider("gmail")
            if hasattr(adapter, "refresh_sender_reputations"):
                await adapter.refresh_sender_reputations(account_id)
        return results, succeeded

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
            runtime_task_state=self._runtime_task_state(),
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
        if self.state.trust_state == "trusted":
            self._invalidate_capability_state()
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
        if self.state.trust_state == "trusted":
            self._invalidate_capability_state()
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
            labels = await adapter.available_labels(account.account_id) if hasattr(adapter, "available_labels") else None
            message_summary = await adapter.message_store_summary(account.account_id) if hasattr(adapter, "message_store_summary") else None
            classification_summary = (
                await adapter.local_classification_summary(account.account_id)
                if hasattr(adapter, "local_classification_summary")
                else None
            )
            sender_reputation = (
                await adapter.sender_reputation_summary(account.account_id)
                if hasattr(adapter, "sender_reputation_summary")
                else None
            )
            model_status = await adapter.training_model_status() if hasattr(adapter, "training_model_status") else None
            spamhaus_summary = await adapter.spamhaus_summary(account.account_id) if hasattr(adapter, "spamhaus_summary") else None
            quota_usage = await adapter.quota_usage_summary(account.account_id) if hasattr(adapter, "quota_usage_summary") else None
            statuses.append(
                {
                    "account": account.model_dump(mode="json"),
                    "mailbox_status": mailbox_status.model_dump(mode="json") if mailbox_status is not None else None,
                    "labels": labels,
                    "message_store": message_summary,
                    "classification_summary": classification_summary,
                    "sender_reputation": sender_reputation,
                    "model_status": model_status,
                    "spamhaus": spamhaus_summary.model_dump(mode="json") if spamhaus_summary is not None else None,
                    "quota_usage": quota_usage.model_dump(mode="json") if quota_usage is not None else None,
                }
            )
        return {
            "provider_id": "gmail",
            "provider_state": await adapter.get_provider_state(),
            "enabled": adapter.get_enabled_status(),
            "fetch_schedule": fetch_schedule.model_dump(mode="json") if fetch_schedule is not None else None,
            "fetch_scheduler": self._gmail_fetch_scheduler_state(),
            "last_hour_pipeline": self._gmail_last_hour_pipeline_state(),
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
            if window == "last_hour":
                result["pipeline"] = await self._run_last_hour_pipeline(
                    account_id=account_id,
                    mode=reason,
                    fetched_count=int(result.get("fetched_count") or 0),
                    correlation_id=correlation_id,
                )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return result

    async def _run_last_hour_pipeline(
        self,
        *,
        account_id: str,
        mode: str,
        fetched_count: int,
        correlation_id: str | None,
    ) -> dict[str, object]:
        started_at = datetime.now(UTC).isoformat()
        state = self._save_gmail_last_hour_pipeline_state(
            mode=mode,
            status="running",
            detail="Running last-hour Gmail pipeline...",
            started_at=started_at,
            updated_at=started_at,
            stages={
                "fetch": {
                    "status": "completed",
                    "detail": f"Fetched {fetched_count} last-hour emails.",
                    "count": fetched_count,
                },
                "spamhaus": {"status": "running", "detail": "Checking pending Spamhaus items...", "count": 0},
                "local_classification": {"status": "idle", "detail": "Waiting", "count": 0},
                "ai_classification": {"status": "idle", "detail": "Waiting", "count": 0},
            },
        )
        adapter = self.provider_registry.get_provider("gmail")
        try:
            spamhaus_summary = await adapter.spamhaus_summary(account_id)
            spamhaus_count = 0
            spamhaus_detail = "No pending Spamhaus items."
            spamhaus_status = "idle"
            if spamhaus_summary.pending_count > 0:
                spamhaus_result = await adapter.check_spamhaus_for_stored_messages(account_id)
                spamhaus_count = int(spamhaus_result.get("checked_count") or 0)
                spamhaus_detail = f"Checked {spamhaus_count} pending Spamhaus items."
                spamhaus_status = "completed"
            state["stages"]["spamhaus"] = {
                "status": spamhaus_status,
                "detail": spamhaus_detail,
                "count": spamhaus_count,
            }
            self._save_gmail_last_hour_pipeline_state(stages=state["stages"], updated_at=datetime.now(UTC).isoformat())

            last_hour_start = datetime.now().astimezone() - timedelta(hours=1)
            recent_messages = adapter.message_store.list_messages_received_since(account_id, since=last_hour_start)
            checked_ids = adapter.message_store.list_spamhaus_checked_message_ids(account_id)
            local_candidates = [
                message
                for message in recent_messages
                if message.message_id in checked_ids and (message.local_label is None or message.local_label == GmailTrainingLabel.UNKNOWN.value)
            ]
            local_stage_status = "idle"
            local_detail = "No last-hour unknown emails needed local classification."
            local_count, ai_candidates = self._classify_candidates_locally(account_id=account_id, candidates=local_candidates)
            if local_count > 0 and hasattr(adapter, "refresh_sender_reputations"):
                await adapter.refresh_sender_reputations(account_id)
            if local_candidates and local_count > 0:
                local_stage_status = "completed"
                local_detail = f"Locally classified {local_count} last-hour emails."
            elif local_candidates:
                local_stage_status = "idle"
                local_detail = "Skipped local classification because no trained local model is available."
            state["stages"]["local_classification"] = {
                "status": local_stage_status,
                "detail": local_detail,
                "count": local_count,
            }
            self._save_gmail_last_hour_pipeline_state(stages=state["stages"], updated_at=datetime.now(UTC).isoformat())

            ai_results, _ = await self._execute_email_classifier_for_messages(
                account_id=account_id,
                messages=ai_candidates,
                target_api_base_url="http://127.0.0.1:9002",
                correlation_id=correlation_id,
            )
            ai_count = len(ai_results)
            state["stages"]["ai_classification"] = {
                "status": "completed" if ai_count > 0 else "idle",
                "detail": (
                    f"Sent {ai_count} last-hour unknown emails to the AI node."
                    if ai_count > 0
                    else "No last-hour unknown emails needed AI classification."
                ),
                "count": ai_count,
            }
            completed_at = datetime.now(UTC).isoformat()
            return self._save_gmail_last_hour_pipeline_state(
                status="completed",
                detail="Last-hour Gmail pipeline completed.",
                stages=state["stages"],
                updated_at=completed_at,
                last_completed_at=completed_at,
            )
        except Exception as exc:
            failed_at = datetime.now(UTC).isoformat()
            return self._save_gmail_last_hour_pipeline_state(
                mode=mode,
                status="failed",
                detail=str(exc),
                stages=state["stages"],
                updated_at=failed_at,
            )

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

    async def gmail_refresh_sender_reputation(
        self,
        *,
        account_id: str = "primary",
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "refresh_sender_reputations"):
            raise ValueError("gmail sender reputation is not available")
        try:
            records = await adapter.refresh_sender_reputations(account_id)
            summary = (
                await adapter.sender_reputation_summary(account_id)
                if hasattr(adapter, "sender_reputation_summary")
                else None
            )
            return {
                "account_id": account_id,
                "refreshed_count": len(records),
                "summary": summary,
            }
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def gmail_training_status(self, *, account_id: str = "primary") -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        return {
            "provider_id": "gmail",
            "account_id": account_id,
            "threshold": self.config.gmail_local_classification_threshold,
            "bootstrap_threshold": self.config.gmail_training_bootstrap_threshold,
            "message_store": await adapter.message_store_summary(account_id) if hasattr(adapter, "message_store_summary") else None,
            "classification_summary": await adapter.local_classification_summary(account_id) if hasattr(adapter, "local_classification_summary") else None,
            "sender_reputation": await adapter.sender_reputation_summary(account_id) if hasattr(adapter, "sender_reputation_summary") else None,
            "dataset_summary": await adapter.training_dataset_summary(
                account_id,
                bootstrap_threshold=self.config.gmail_training_bootstrap_threshold,
            )
            if hasattr(adapter, "training_dataset_summary")
            else None,
            "model_status": await adapter.training_model_status() if hasattr(adapter, "training_model_status") else None,
        }

    async def gmail_sender_reputation_summary(
        self,
        *,
        account_id: str = "primary",
        limit: int = 20,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "sender_reputation_summary"):
            raise ValueError("gmail sender reputation is not available")
        return await adapter.sender_reputation_summary(account_id, limit=limit)

    async def gmail_sender_reputation_detail(
        self,
        *,
        account_id: str = "primary",
        entity_type: str,
        sender_value: str,
        message_limit: int = 10,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "sender_reputation_detail"):
            raise ValueError("gmail sender reputation is not available")
        if entity_type not in {"email", "domain", "business_domain"}:
            raise ValueError("entity_type must be email, domain, or business_domain")
        detail = await adapter.sender_reputation_detail(
            account_id,
            entity_type=entity_type,
            sender_value=sender_value.strip().lower(),
            message_limit=message_limit,
        )
        if detail is None:
            raise ValueError("sender reputation record was not found")
        return detail

    async def gmail_save_sender_reputation_manual_rating(
        self,
        *,
        account_id: str = "primary",
        entity_type: str,
        sender_value: str,
        manual_rating: float | None,
        note: str | None = None,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "save_sender_reputation_manual_rating"):
            raise ValueError("gmail sender reputation is not available")
        normalized_entity_type = (entity_type or "").strip().lower()
        if normalized_entity_type not in {"email", "domain", "business_domain"}:
            raise ValueError("entity_type must be email, domain, or business_domain")
        normalized_sender_value = (sender_value or "").strip().lower()
        if not normalized_sender_value:
            raise ValueError("sender_value is required")
        normalized_note = (note or "").strip() or None
        normalized_manual_rating = None if manual_rating is None else float(manual_rating)
        if normalized_manual_rating is not None and not -6.0 <= normalized_manual_rating <= 6.0:
            raise ValueError("manual_rating must be between -6 and 6")
        try:
            return await adapter.save_sender_reputation_manual_rating(
                account_id,
                entity_type=normalized_entity_type,
                sender_value=normalized_sender_value,
                manual_rating=normalized_manual_rating,
                note=normalized_note,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

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
            result = await adapter.save_manual_classifications(account_id, payload)
            # Debug-only visibility: surface the same user notifications when Training-page
            # manual classification saves assign action_required/order labels.
            for item in payload.items:
                self._notify_for_new_email_classification(
                    account_id=account_id,
                    message_id=item.message_id,
                    classification_label=item.label,
                    confidence=1.0,
                    source_component="gmail_training_manual_classification",
                )
            return result
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def gmail_training_train_model(
        self,
        *,
        account_id: str = "primary",
        minimum_confidence: float | None = None,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "train_local_model"):
            raise ValueError("gmail training actions are not available")
        try:
            return await adapter.train_local_model(
                account_id,
                bootstrap_threshold=self.config.gmail_training_bootstrap_threshold,
                minimum_confidence=minimum_confidence,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def gmail_training_semi_auto_batch(self, *, account_id: str = "primary", limit: int = 20) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "semi_auto_training_batch"):
            raise ValueError("gmail training actions are not available")
        try:
            return await adapter.semi_auto_training_batch(
                account_id,
                threshold=self.config.gmail_local_classification_threshold,
                limit=limit,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def gmail_training_classified_batch(
        self,
        *,
        account_id: str = "primary",
        label: GmailTrainingLabel,
        limit: int = 40,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "classified_training_batch"):
            raise ValueError("gmail training actions are not available")
        try:
            return await adapter.classified_training_batch(account_id, label=label, limit=limit)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    async def gmail_training_save_semi_auto_review(
        self,
        payload: GmailSemiAutoClassificationBatchInput,
        *,
        account_id: str = "primary",
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        if not hasattr(adapter, "save_semi_auto_review"):
            raise ValueError("gmail training actions are not available")
        try:
            result = await adapter.save_semi_auto_review(account_id, payload)
            # Debug-only visibility: surface the same user notifications when Training-page
            # review saves assign action_required/order labels.
            for item in payload.items:
                self._notify_for_new_email_classification(
                    account_id=account_id,
                    message_id=item.message_id,
                    classification_label=item.selected_label,
                    confidence=1.0 if item.selected_label != item.predicted_label else item.predicted_confidence,
                    source_component="gmail_training_semi_auto_review",
                )
            return result
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
        self.state_store.save(self.state)
        await self._update_operational_readiness()

    def _ensure_gmail_status_polling(self) -> None:
        if self.gmail_status_task is None or self.gmail_status_task.done():
            GMAIL_POLL_LOGGER.info(
                "Gmail status polling loop starting",
                extra={"event_data": {"interval_seconds": self.config.gmail_status_poll_interval_seconds}},
            )
            self.gmail_status_task = asyncio.create_task(self._gmail_status_loop())

    def _ensure_gmail_fetch_polling(self) -> None:
        if self.gmail_fetch_task is None or self.gmail_fetch_task.done():
            self._save_gmail_fetch_scheduler_state(
                loop_enabled=True,
                loop_active=True,
                status="running",
                detail="Gmail fetch scheduler loop is running.",
                last_error=None,
                last_error_at=None,
            )
            self._gmail_fetch_notification_state = "healthy"
            self.gmail_fetch_task = asyncio.create_task(self._gmail_fetch_loop())

    async def _gmail_status_loop(self) -> None:
        while True:
            try:
                await self._refresh_gmail_status()
            except Exception as exc:
                GMAIL_POLL_LOGGER.error(
                    "Gmail status polling loop failed",
                    extra={"event_data": {"detail": str(exc)}},
                )
            await asyncio.sleep(self.config.gmail_status_poll_interval_seconds)

    async def _refresh_gmail_status(self) -> None:
        gmail_adapter = self.provider_registry.get_provider("gmail")
        accounts = await gmail_adapter.list_accounts()
        eligible_accounts = [account for account in accounts if account.status in {"connected", "token_exchanged", "degraded"}]
        GMAIL_POLL_LOGGER.info(
            "Gmail status polling pass started",
            extra={
                "event_data": {
                    "account_count": len(accounts),
                    "eligible_account_count": len(eligible_accounts),
                }
            },
        )
        for account in accounts:
            if account.status in {"connected", "token_exchanged", "degraded"}:
                mailbox_status = await gmail_adapter.refresh_mailbox_status(account.account_id)
                GMAIL_POLL_LOGGER.info(
                    "Gmail status polling pass refreshed account",
                    extra={
                        "event_data": {
                            "account_id": account.account_id,
                            "checked_at": mailbox_status.checked_at.isoformat(),
                            "unread_inbox_count": mailbox_status.unread_inbox_count,
                            "unread_today_count": mailbox_status.unread_today_count,
                            "unread_last_hour_count": mailbox_status.unread_last_hour_count,
                        }
                    },
                )

    async def _gmail_fetch_loop(self) -> None:
        while True:
            try:
                await self._run_due_gmail_fetches()
            except Exception as exc:
                failed_at = datetime.now(UTC).isoformat()
                self._save_gmail_fetch_scheduler_state(
                    loop_enabled=True,
                    loop_active=True,
                    status="error",
                    detail="Gmail fetch scheduler loop hit an error.",
                    last_error=str(exc),
                    last_error_at=failed_at,
                    last_checked_at=failed_at,
                )
                self._set_gmail_fetch_notification_state("error", f"Gmail fetch scheduler failed: {exc}")
                LOGGER.error(
                    "Scheduled Gmail fetch loop failed",
                    extra={"event_data": {"detail": str(exc)}},
                )
            await asyncio.sleep(self._seconds_until_next_minute())

    async def _run_due_gmail_fetches(self) -> None:
        gmail_adapter = self.provider_registry.get_provider("gmail")
        if not gmail_adapter.get_enabled_status():
            self._set_gmail_fetch_notification_state(
                "warning",
                "Gmail fetch scheduling is paused because the Gmail provider is disabled.",
            )
            self._save_gmail_fetch_scheduler_state(
                status="idle",
                detail="Gmail fetch scheduler is idle because Gmail is disabled.",
                last_checked_at=datetime.now(UTC).isoformat(),
                last_due_windows=[],
            )
            return
        accounts = await gmail_adapter.list_accounts()
        eligible_accounts = [account for account in accounts if account.status in {"connected", "token_exchanged", "degraded"}]
        if not eligible_accounts:
            self._set_gmail_fetch_notification_state(
                "warning",
                "Gmail fetch scheduling is paused because no eligible Gmail account is connected.",
            )
            self._save_gmail_fetch_scheduler_state(
                status="idle",
                detail="Gmail fetch scheduler is idle because no eligible Gmail account is connected.",
                last_checked_at=datetime.now(UTC).isoformat(),
                last_due_windows=[],
            )
            return

        schedule_state = await gmail_adapter.fetch_schedule_state() if hasattr(gmail_adapter, "fetch_schedule_state") else None
        now = datetime.now().astimezone()
        due_windows = self._due_gmail_fetch_windows(now, schedule_state)
        checked_at = datetime.now(UTC).isoformat()
        self._save_gmail_fetch_scheduler_state(
            status="running" if due_windows else "idle",
            detail=(
                f"Scheduled Gmail fetch due for {', '.join(window for window, _ in due_windows)}."
                if due_windows
                else "No scheduled Gmail fetch windows are due right now."
            ),
            last_checked_at=checked_at,
            last_due_windows=[{"window": window, "slot_key": slot_key} for window, slot_key in due_windows],
        )
        self._set_gmail_fetch_notification_state("healthy", "Gmail fetch scheduling is running normally.")
        for account in eligible_accounts:
            for window, slot_key in due_windows:
                attempt_at = datetime.now(UTC).isoformat()
                LOGGER.info(
                    "Scheduled Gmail fetch attempt",
                    extra={
                        "event_data": {
                            "account_id": account.account_id,
                            "window": window,
                            "slot_key": slot_key,
                        }
                    },
                )
                await self.gmail_fetch_messages(
                    window,
                    account_id=account.account_id,
                    reason="scheduled",
                    slot_key=slot_key,
                )
                success_at = datetime.now(UTC).isoformat()
                self._save_gmail_fetch_scheduler_state(
                    status="completed",
                    detail=f"Scheduled Gmail fetch completed for {window}.",
                    last_attempt_at=attempt_at,
                    last_success_at=success_at,
                    last_error=None,
                    last_error_at=None,
                )
                LOGGER.info(
                    "Scheduled Gmail fetch completed",
                    extra={
                        "event_data": {
                            "account_id": account.account_id,
                            "window": window,
                            "slot_key": slot_key,
                        }
                    },
                )
        await self._run_due_hourly_batch_classification(now)

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
        if (
            schedule_map["yesterday"]
            and (now.hour > 0 or (now.hour == 0 and now.minute >= 1))
            and getattr(yesterday_state, "last_slot_key", None) != schedule_map["yesterday"]
        ):
            due.append(("yesterday", schedule_map["yesterday"]))

        today_state = getattr(schedule_state, "today", None)
        if (
            schedule_map["today"]
            and getattr(today_state, "last_slot_key", None) != schedule_map["today"]
            and now.hour // 6 == int(schedule_map["today"].rsplit(":", 1)[-1])
        ):
            due.append(("today", schedule_map["today"]))

        last_hour_state = getattr(schedule_state, "last_hour", None)
        if schedule_map["last_hour"] and getattr(last_hour_state, "last_slot_key", None) != schedule_map["last_hour"]:
            due.append(("last_hour", schedule_map["last_hour"]))

        return due

    async def _run_due_hourly_batch_classification(self, now: datetime) -> None:
        slot_key = self._gmail_hourly_batch_slot_key(now)
        if slot_key is None or self.state.gmail_hourly_batch_classification_slot_key == slot_key:
            return
        try:
            LOGGER.info(
                "Scheduled hourly Gmail batch classification starting",
                extra={"event_data": {"slot_key": slot_key}},
            )
            await self.runtime_execute_email_classifier_batch(
                RuntimePromptExecutionRequestInput(target_api_base_url="http://127.0.0.1:9002")
            )
            self.state.gmail_hourly_batch_classification_slot_key = slot_key
            self.state_store.save(self.state)
            LOGGER.info(
                "Scheduled hourly Gmail batch classification completed",
                extra={"event_data": {"slot_key": slot_key}},
            )
        except Exception as exc:
            LOGGER.error(
                "Scheduled hourly Gmail batch classification failed",
                extra={"event_data": {"slot_key": slot_key, "detail": str(exc)}},
            )

    def _gmail_hourly_batch_slot_key(self, now: datetime) -> str | None:
        local_now = now.astimezone()
        if local_now.minute >= 5:
            return None
        return local_now.replace(minute=0, second=0, microsecond=0).isoformat()

    def _gmail_fetch_slot_key(self, window: str, now: datetime) -> str | None:
        local_now = now.astimezone()
        if window == "yesterday":
            return (local_now - timedelta(days=1)).date().isoformat()
        if window == "today":
            return f"{local_now.date().isoformat()}:{local_now.hour // 6}"
        if window == "last_hour":
            slot_time = local_now.replace(minute=(local_now.minute // 5) * 5, second=0, microsecond=0)
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
