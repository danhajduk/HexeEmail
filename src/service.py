from __future__ import annotations

import asyncio
import socket
import uuid
from datetime import UTC, datetime

from version import __version__
from config import AppConfig
from core_client import CoreApiClient, FinalizeResponse, OnboardingSessionRequest
from logging_utils import get_logger
from models import OnboardingStatusResponse, RuntimeState, StatusResponse, TrustMaterial
from mqtt import MQTTManager
from providers.registry import ProviderRegistry
from state_store import RuntimeStateStore, StateCorruptionError, TrustMaterialStore


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
        self.trust_store = TrustMaterialStore(config.trust_material_file)
        self.core_client = core_client or CoreApiClient(config)
        self.mqtt_manager = mqtt_manager or MQTTManager(
            heartbeat_seconds=config.mqtt_heartbeat_seconds,
            on_heartbeat=self._record_heartbeat,
        )
        self.provider_registry = ProviderRegistry(config)
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
                    "node_name": self.config.node_name,
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

    async def _resume_runtime(self) -> None:
        if self.state.trust_state == "trusted" and self.trust_material is not None:
            LOGGER.info("Trusted state detected, skipping onboarding")
            self._connect_mqtt_if_possible()
            return
        if self.state.onboarding_status == "pending" and self.state.onboarding_session_id:
            LOGGER.info("Pending onboarding session found, resuming finalize polling")
            self._ensure_polling()
            return
        if self.state.onboarding_status == "not_started" or not self.state.onboarding_session_id:
            await self.start_onboarding()
            return
        if self.state.onboarding_status in {"rejected", "expired", "invalid", "consumed"}:
            LOGGER.warning(
                "Terminal onboarding state found without trust, starting fresh onboarding",
                extra={"event_data": {"onboarding_status": self.state.onboarding_status}},
            )
            await self.start_onboarding()
            return
        self.startup_error = "corrupted state: unable to determine startup path"
        self.ready = False

    async def start_onboarding(self) -> None:
        correlation_id = str(uuid.uuid4())
        request = OnboardingSessionRequest(
            node_name=self.config.node_name,
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            protocol_version=self.config.onboarding_protocol_version,
            node_nonce=self.config.node_nonce,
            hostname=socket.gethostname(),
        )
        session = await self.core_client.create_onboarding_session(request, correlation_id)
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

    def _ensure_polling(self) -> None:
        if self.polling_task is None or self.polling_task.done():
            self.polling_task = asyncio.create_task(self._poll_finalize_loop())

    async def _poll_finalize_loop(self) -> None:
        while self.state.onboarding_session_id:
            correlation_id = str(uuid.uuid4())
            finalize = await self.core_client.finalize_onboarding(
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

    def onboarding_status(self) -> OnboardingStatusResponse:
        return OnboardingStatusResponse(
            node_name=self.config.node_name,
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            session_id=self.state.onboarding_session_id,
            approval_url=self.state.approval_url,
            onboarding_status=self.state.onboarding_status,
            trust_state=self.state.trust_state,
            node_id=self.state.node_id,
            expires_at=self.state.onboarding_expires_at,
            last_error=self.state.last_error,
        )

    def status(self) -> StatusResponse:
        return StatusResponse(
            node_name=self.config.node_name,
            node_type=self.config.node_type,
            node_software_version=self.config.node_software_version,
            trust_state=self.state.trust_state,
            node_id=self.state.node_id,
            mqtt_connection_status=self.mqtt_manager.status.state,
            onboarding_status=self.state.onboarding_status,
            providers=self.provider_registry.provider_ids(),
        )


import contextlib
