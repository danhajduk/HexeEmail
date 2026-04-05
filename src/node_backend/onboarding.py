from __future__ import annotations

import asyncio
import contextlib
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx


CORE_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")


class OnboardingManager:
    def __init__(self, service: Any) -> None:
        self.service = service

    def reset_onboarding_state(self) -> None:
        self.service.background_tasks.cancel_finalize_polling()
        self.service.state.onboarding_session_id = None
        self.service.state.approval_url = None
        self.service.state.onboarding_status = "not_started"
        self.service.state.onboarding_expires_at = None
        self.service.state.node_id = None
        self.service.state.paired_core_id = None
        self.service.state.trust_state = "untrusted"
        self.service.state.trust_token_present = False
        self.service.state.mqtt_credentials_present = False
        self.service.state.operational_mqtt_host = None
        self.service.state.operational_mqtt_port = None
        self.service.state.last_finalize_status = None
        self.service.state.last_error = None
        self.service.state.trusted_at = None
        self.service.state.last_poll_at = None
        self.service.state_store.save(self.service.state)

    def clear_trust_and_onboarding_state(self) -> None:
        self.reset_onboarding_state()
        self.service.trust_store.clear()
        self.service.trust_material = None
        self.service.mqtt_manager.disconnect()

    @staticmethod
    def normalize_core_base_url(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value)
        if not parsed.scheme:
            return f"http://{value}"
        return value.rstrip("/")

    def normalize_selected_task_capabilities(self, values: list[str] | None) -> list[str]:
        available = set(self.service.available_task_capabilities)
        normalized: list[str] = []
        for value in values or []:
            candidate = str(value or "").strip()
            if candidate and candidate in available and candidate not in normalized:
                normalized.append(candidate)
        return normalized

    def resolve_advertised_host(self) -> str:
        targets: list[tuple[str, int]] = []
        core_host = urlparse(self.service.effective_core_base_url() or "").hostname
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

    def advertised_api_base_url(self) -> str:
        host = self.resolve_advertised_host()
        return f"http://{host}:{self.service.config.api_port}/api"

    def advertised_ui_endpoint(self) -> str:
        host = self.resolve_advertised_host()
        return f"http://{host}:{self.service.config.ui_port}"

    @staticmethod
    def normalize_platform_core_id(value: str | None) -> str | None:
        candidate = str(value or "").strip().lower()
        if CORE_ID_PATTERN.fullmatch(candidate):
            return candidate
        return None

    @staticmethod
    def extract_hexe_core_uuid(value: str | None) -> str | None:
        if not value:
            return None
        host = urlparse(value).hostname or ""
        if host.endswith(".hexe-ai.com"):
            candidate = host.removesuffix(".hexe-ai.com")
            if candidate and candidate != "hexe-ai":
                return candidate
        return None

    def format_core_error(self, exc: httpx.HTTPError) -> str:
        base_url = self.service.effective_core_base_url() or "configured Core URL"
        if isinstance(exc, httpx.ConnectError):
            return f"Unable to reach Core at {base_url}. Check the host, port, and network."
        if isinstance(exc, httpx.TimeoutException):
            return f"Timed out while contacting Core at {base_url}."
        if isinstance(exc, httpx.HTTPStatusError):
            detail_message = self.extract_core_error_message(exc.response)
            if detail_message:
                return detail_message
            return f"Core returned {exc.response.status_code} during onboarding start."
        if isinstance(exc, httpx.UnsupportedProtocol):
            return f"Core URL must include a valid host. Current value: {base_url}"
        return f"Failed to contact Core at {base_url}: {exc.__class__.__name__}"

    @staticmethod
    def extract_core_error_message(response: httpx.Response) -> str | None:
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
