from __future__ import annotations

import asyncio
import contextlib
import json
import re
import socket
import uuid
from email.utils import getaddresses, parseaddr
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
from node_backend import (
    AiNodeGateway,
    BackgroundTaskManager,
    EmailProviderGateway,
    GovernanceManager,
    NotificationManager,
    OnboardingManager,
    ProviderManager,
    RuntimeManager,
    ScheduleTemplate,
)
from node_models.config import OperatorConfig, OperatorConfigInput
from node_models.node import (
    GmailConnectStartResponse,
    GmailOAuthCallbackResponse,
    MqttHealthResponse,
    OnboardingStatusResponse,
    OperatorConfigResponse,
    StatusResponse,
    TrustMaterial,
    UiBootstrapResponse,
)
from node_models.notifications import (
    NodeNotificationRequest,
    NodeNotificationResult,
    NotificationContent,
    NotificationDelivery,
    NotificationEvent,
    NotificationSourceHint,
    NotificationTargets,
)
from node_models.runtime import (
    CoreServiceAuthorizeRequestInput,
    CoreServiceResolveRequestInput,
    RuntimeDirectExecutionRequestInput,
    RuntimePromptExecutionRequestInput,
    RuntimePromptReviewRequestInput,
    RuntimePromptSyncRequestInput,
    RuntimeState,
    RuntimeTaskSettingsInput,
    TaskRoutingPreviewResponse,
    TaskRoutingRequestInput,
)
from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.config_store import GmailProviderConfigError, GmailProviderConfigStore
from providers.gmail.models import (
    GmailManualClassificationBatchInput,
    GmailOAuthConfig,
    GmailSemiAutoClassificationBatchInput,
    GmailShipmentRecord,
    GmailTrainingLabel,
)
from providers.gmail.order_flow import GmailOrderPhase1Processor
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
        self.available_task_capabilities = list(AVAILABLE_TASK_CAPABILITIES)
        self.operator_config = OperatorConfig(core_base_url=config.core_base_url, node_name=config.node_name)
        self.state = RuntimeState()
        self.trust_material: TrustMaterial | None = None
        self.live = True
        self.ready = False
        self.startup_error: str | None = None
        self.gmail_order_flow = GmailOrderPhase1Processor()
        self.runtime = RuntimeManager(self)
        self.ai_gateway = AiNodeGateway(self)
        self.onboarding = OnboardingManager(self)
        self.notifications = NotificationManager(self)
        self.providers = ProviderManager(self)
        self.governance = GovernanceManager(self)
        self.background_tasks = BackgroundTaskManager(self)
        self.provider_registry = self.providers.build_provider_registry()
        self.email_provider_gateway = EmailProviderGateway(self)

    @staticmethod
    def _default_runtime_task_state() -> dict[str, object]:
        return RuntimeManager.default_runtime_task_state()

    def _runtime_task_state(self) -> dict[str, object]:
        return self.runtime.runtime_task_state()

    def _save_runtime_task_state(self, **updates: object) -> dict[str, object]:
        return self.runtime.save_runtime_task_state(**updates)

    def _runtime_ai_calls_enabled(self) -> bool:
        return self.runtime.runtime_ai_calls_enabled()

    def _runtime_ai_disabled_message(self) -> str:
        return self.runtime.runtime_ai_disabled_message()

    def _runtime_provider_calls_enabled(self) -> bool:
        return self.runtime.runtime_provider_calls_enabled()

    def _runtime_provider_disabled_message(self) -> str:
        return self.runtime.runtime_provider_disabled_message()

    @staticmethod
    def _default_gmail_last_hour_pipeline_state() -> dict[str, object]:
        return BackgroundTaskManager.default_gmail_last_hour_pipeline_state()

    @staticmethod
    def _default_gmail_fetch_scheduler_state() -> dict[str, object]:
        return BackgroundTaskManager.default_gmail_fetch_scheduler_state()

    def _gmail_fetch_scheduler_state(self) -> dict[str, object]:
        return self.background_tasks.gmail_fetch_scheduler_state()

    def _save_gmail_fetch_scheduler_state(self, **updates: object) -> dict[str, object]:
        return self.background_tasks.save_gmail_fetch_scheduler_state(**updates)

    def _gmail_last_hour_pipeline_state(self) -> dict[str, object]:
        return self.background_tasks.gmail_last_hour_pipeline_state()

    def _save_gmail_last_hour_pipeline_state(self, **updates: object) -> dict[str, object]:
        return self.background_tasks.save_gmail_last_hour_pipeline_state(**updates)

    @staticmethod
    def _next_daily_run(now: datetime, *, hour: int, minute: int) -> datetime:
        return BackgroundTaskManager.next_daily_run(now, hour=hour, minute=minute)

    @staticmethod
    def _next_today_window_run(now: datetime) -> datetime:
        return BackgroundTaskManager.next_today_window_run(now)

    @staticmethod
    def _next_five_minute_run(now: datetime) -> datetime:
        return BackgroundTaskManager.next_five_minute_run(now)

    @staticmethod
    def _next_hourly_run(now: datetime) -> datetime:
        return BackgroundTaskManager.next_hourly_run(now)

    @staticmethod
    def _next_weekly_run(now: datetime, *, weekday: int = 0, hour: int = 0, minute: int = 1) -> datetime:
        return BackgroundTaskManager.next_weekly_run(now, weekday=weekday, hour=hour, minute=minute)

    @staticmethod
    def _next_bi_weekly_run(
        now: datetime,
        *,
        anchor: tuple[int, int, int] = (2026, 1, 5),
        weekday: int = 0,
        hour: int = 0,
        minute: int = 1,
    ) -> datetime:
        return BackgroundTaskManager.next_bi_weekly_run(now, anchor=anchor, weekday=weekday, hour=hour, minute=minute)

    @staticmethod
    def _next_monthly_run(now: datetime, *, day: int = 1, hour: int = 0, minute: int = 1) -> datetime:
        return BackgroundTaskManager.next_monthly_run(now, day=day, hour=hour, minute=minute)

    @staticmethod
    def _next_every_other_day_run(
        now: datetime,
        *,
        anchor: tuple[int, int, int] = (2026, 1, 1),
        hour: int = 0,
        minute: int = 1,
    ) -> datetime:
        return BackgroundTaskManager.next_every_other_day_run(now, anchor=anchor, hour=hour, minute=minute)

    @staticmethod
    def _next_twice_a_week_run(now: datetime, *, weekdays: tuple[int, int] = (0, 3), hour: int = 0, minute: int = 1) -> datetime:
        return BackgroundTaskManager.next_twice_a_week_run(now, weekdays=weekdays, hour=hour, minute=minute)

    @classmethod
    def _schedule_templates(cls) -> dict[str, ScheduleTemplate]:
        return BackgroundTaskManager.schedule_templates()

    @classmethod
    def _schedule_template_detail(cls, schedule_name: str) -> str:
        return BackgroundTaskManager.schedule_template_detail(schedule_name)

    @classmethod
    def _schedule_template_next_run(cls, schedule_name: str, now: datetime) -> datetime | None:
        return BackgroundTaskManager.schedule_template_next_run(schedule_name, now)

    @classmethod
    def _scheduled_task_entry(
        cls,
        *,
        task_id: str,
        title: str,
        group: str,
        schedule_name: str,
        status: str,
        last_execution_at: str | None,
        next_execution_at: str | None,
        last_reason: str | None,
        detail: str,
        last_slot_key: str | None = None,
        schedule_detail: str | None = None,
    ) -> dict[str, object]:
        return BackgroundTaskManager.scheduled_task_entry(
            task_id=task_id,
            title=title,
            group=group,
            schedule_name=schedule_name,
            status=status,
            last_execution_at=last_execution_at,
            next_execution_at=next_execution_at,
            last_reason=last_reason,
            detail=detail,
            last_slot_key=last_slot_key,
            schedule_detail=schedule_detail,
        )

    @classmethod
    def _scheduled_task_legend(cls) -> list[dict[str, str]]:
        return BackgroundTaskManager.scheduled_task_legend()

    def _scheduled_tasks_snapshot(self) -> list[dict[str, object]]:
        return self.background_tasks.scheduled_tasks_snapshot()

    def _tracked_orders_snapshot(self) -> list[dict[str, object]]:
        gmail_adapter = self.provider_registry.get_provider("gmail")
        records = gmail_adapter.message_store.list_all_shipment_records(limit=500)
        return [
            {
                "account_id": record.account_id,
                "record_id": record.record_id,
                "seller": record.seller,
                "carrier": record.carrier,
                "order_number": record.order_number,
                "tracking_number": record.tracking_number,
                "domain": record.domain,
                "last_known_status": record.last_known_status,
                "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at is not None else None,
                "status_updated_at": record.status_updated_at.isoformat() if record.status_updated_at is not None else None,
                "updated_at": record.updated_at.isoformat() if record.updated_at is not None else None,
            }
            for record in records
        ]

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

    @staticmethod
    def _parse_action_decision_output(output: object) -> dict[str, object] | None:
        def is_action_decision_payload(value: object) -> bool:
            return isinstance(value, dict) and (
                "primary_label" in value
                or "recommended_actions" in value
                or "human_review_required" in value
            )

        def parse_json_text(value: object) -> dict[str, object] | None:
            if not isinstance(value, str):
                return None
            try:
                parsed = json.loads(value)
            except Exception:
                return None
            return parsed if isinstance(parsed, dict) else None

        if is_action_decision_payload(output):
            return output
        if isinstance(output, str):
            return parse_json_text(output)
        if not isinstance(output, dict):
            return None

        for key in ("result", "parsed", "json", "data", "output"):
            candidate = output.get(key)
            if is_action_decision_payload(candidate):
                return candidate
            parsed_candidate = parse_json_text(candidate)
            if is_action_decision_payload(parsed_candidate):
                return parsed_candidate

        response_payload = output.get("response")
        if isinstance(response_payload, dict):
            for key in ("output_text", "text", "content"):
                candidate = response_payload.get(key)
                if is_action_decision_payload(candidate):
                    return candidate
                parsed_candidate = parse_json_text(candidate)
                if is_action_decision_payload(parsed_candidate):
                    return parsed_candidate
                if isinstance(candidate, list):
                    for item in candidate:
                        if is_action_decision_payload(item):
                            return item
                        if isinstance(item, dict):
                            for nested_key in ("text", "output_text", "json", "parsed"):
                                nested_candidate = item.get(nested_key)
                                if is_action_decision_payload(nested_candidate):
                                    return nested_candidate
                                parsed_nested = parse_json_text(nested_candidate)
                                if is_action_decision_payload(parsed_nested):
                                    return parsed_nested

        text = output.get("text")
        parsed_text = parse_json_text(text)
        if is_action_decision_payload(parsed_text):
            return parsed_text
        return None

    @classmethod
    def _validate_json_schema_value(
        cls,
        value: object,
        schema: dict[str, object],
        *,
        path: str = "$",
    ) -> str | None:
        schema_type = schema.get("type")
        allowed_types = schema_type if isinstance(schema_type, list) else [schema_type] if schema_type is not None else []
        if allowed_types:
            type_ok = False
            for allowed_type in allowed_types:
                if allowed_type == "null" and value is None:
                    type_ok = True
                elif allowed_type == "object" and isinstance(value, dict):
                    type_ok = True
                elif allowed_type == "array" and isinstance(value, list):
                    type_ok = True
                elif allowed_type == "string" and isinstance(value, str):
                    type_ok = True
                elif allowed_type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
                    type_ok = True
                elif allowed_type == "boolean" and isinstance(value, bool):
                    type_ok = True
            if not type_ok:
                return f"{path}: expected {allowed_types}, got {type(value).__name__}"

        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and value not in enum_values:
            return f"{path}: expected one of {enum_values}, got {value!r}"

        if value is None:
            return None

        if isinstance(value, dict):
            properties = schema.get("properties")
            properties_map = properties if isinstance(properties, dict) else {}
            required = schema.get("required")
            if isinstance(required, list):
                for key in required:
                    if isinstance(key, str) and key not in value:
                        return f"{path}: missing required field {key}"
            if schema.get("additionalProperties") is False:
                for key in value.keys():
                    if key not in properties_map:
                        return f"{path}: unexpected field {key}"
            for key, child_schema in properties_map.items():
                if key not in value or not isinstance(child_schema, dict):
                    continue
                error = cls._validate_json_schema_value(value[key], child_schema, path=f"{path}.{key}")
                if error is not None:
                    return error
            return None

        if isinstance(value, list):
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    error = cls._validate_json_schema_value(item, item_schema, path=f"{path}[{index}]")
                    if error is not None:
                        return error
            return None

        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and isinstance(value, (int, float)) and value < minimum:
            return f"{path}: expected >= {minimum}, got {value}"
        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)) and isinstance(value, (int, float)) and value > maximum:
            return f"{path}: expected <= {maximum}, got {value}"
        return None

    @classmethod
    def _validate_action_decision_payload(
        cls,
        value: object,
        schema: dict[str, object],
    ) -> dict[str, object] | None:
        if not isinstance(value, dict):
            return None
        error = cls._validate_json_schema_value(value, schema)
        if error is not None:
            AI_LOGGER.warning(
                "AI action decision output failed schema validation",
                extra={"event_data": {"detail": error}},
            )
            return None
        return value

    @classmethod
    def _action_decision_debug_payload(
        cls,
        *,
        prompt_version: str,
        execution_payload: object,
        parsed_output: object,
        validation_error: str | None,
        target_api_base_url: str,
    ) -> dict[str, object]:
        return {
            "prompt_version": prompt_version,
            "target_api_base_url": target_api_base_url,
            "execution_payload": execution_payload if isinstance(execution_payload, dict) else {"raw": execution_payload},
            "parsed_output": parsed_output if isinstance(parsed_output, dict) else None,
            "validation_error": validation_error,
        }

    def _default_ai_runtime_target_api_base_url(self) -> str:
        return self._normalize_target_api_base_url(self.state.runtime_prompt_sync_target_api_base_url)

    @staticmethod
    def _message_payload_json(raw_payload: str | None) -> dict[str, object]:
        if not raw_payload:
            return {}
        try:
            payload = json.loads(raw_payload)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _message_header_map(payload: dict[str, object]) -> dict[str, str]:
        headers = payload.get("payload", {}).get("headers") if isinstance(payload.get("payload"), dict) else []
        header_map: dict[str, str] = {}
        if isinstance(headers, list):
            for header in headers:
                if not isinstance(header, dict):
                    continue
                name = header.get("name")
                value = header.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    header_map[name.lower()] = value
        return header_map

    @staticmethod
    def _message_has_attachment(payload: dict[str, object]) -> bool:
        root_payload = payload.get("payload")
        if not isinstance(root_payload, dict):
            return False
        parts = root_payload.get("parts")
        if not isinstance(parts, list):
            return False
        return any(isinstance(part, dict) and str(part.get("filename") or "").strip() for part in parts)

    def _build_action_decision_inputs(
        self,
        *,
        account_id: str,
        message,
        full_message_text: str | None = None,
        full_message_html: str | None = None,
        full_message_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        adapter = self.provider_registry.get_provider("gmail")
        account_record = adapter.account_store.load_account(account_id)
        my_addresses = [account_record.email_address] if account_record is not None and account_record.email_address else []
        payload = full_message_payload if isinstance(full_message_payload, dict) else self._message_payload_json(message.raw_payload)
        header_map = self._message_header_map(payload)
        from_name, from_email = parseaddr(message.sender or header_map.get("from", ""))
        to_recipients = [address for _, address in getaddresses([header_map.get("to", "")]) if address]
        cc_recipients = [address for _, address in getaddresses([header_map.get("cc", "")]) if address]
        if not to_recipients:
            to_recipients = [recipient for recipient in message.recipients if recipient]
        extracted_text = str(full_message_text or "").strip()
        extracted_html = str(full_message_html or "").strip()
        normalized_body_text = extracted_text or normalize_email_for_classifier(message, my_addresses=my_addresses)
        subject_text = str(message.subject or "").strip()
        prompt_parts = [f"subject: {subject_text}", "mail body:", normalized_body_text]
        if extracted_html:
            prompt_parts.extend(["mail html:", extracted_html])
        prompt_text = "\n".join(prompt_parts)
        return {
            "text": prompt_text,
            "account_id": account_id,
            "message_id": message.message_id,
            "thread_id": message.thread_id or "",
            "received_at": message.received_at.isoformat(),
            "subject": subject_text,
            "from_name": from_name or "",
            "from_email": from_email or "",
            "to_recipients": to_recipients,
            "cc_recipients": cc_recipients,
            "labels": list(message.label_ids or []),
            "has_attachments": self._message_has_attachment(payload),
            "body_text": normalized_body_text,
            "body_html": extracted_html,
            "snippet": message.snippet or "",
        }

    @staticmethod
    def _action_decision_sender_domain(message) -> str | None:
        _, sender_email = parseaddr(getattr(message, "sender", "") or "")
        if "@" not in sender_email:
            return None
        return str(sender_email.rsplit("@", 1)[-1]).strip().lower() or None

    @staticmethod
    def _action_decision_canonical_party(value: object) -> str | None:
        normalized = " ".join(str(value or "").strip().split()).lower()
        return normalized or None

    @staticmethod
    def _action_decision_canonical_identifier(value: object) -> str | None:
        normalized = re.sub(r"[^0-9A-Z-]", "", str(value or "").strip().upper())
        return normalized or None

    def _upsert_tracked_order_from_action_decision(
        self,
        *,
        account_id: str,
        message,
        action_decision: dict[str, object],
    ) -> None:
        primary_label = str(action_decision.get("primary_label") or "").strip().upper()
        tracking_signals = action_decision.get("tracking_signals")
        if not isinstance(tracking_signals, dict):
            return
        is_shipment_related = bool(tracking_signals.get("is_shipment_related"))
        if primary_label not in {"ORDER", "SHIPMENT"} and not is_shipment_related:
            return

        seller = self._action_decision_canonical_party(tracking_signals.get("seller"))
        carrier = self._action_decision_canonical_party(tracking_signals.get("carrier"))
        order_number = self._action_decision_canonical_identifier(tracking_signals.get("order_number"))
        tracking_number = self._action_decision_canonical_identifier(tracking_signals.get("tracking_number"))
        last_known_status = str(tracking_signals.get("current_status") or "").strip() or None
        if not tracking_number and primary_label == "ORDER":
            last_known_status = "ordered"
        domain = self._action_decision_sender_domain(message)
        if not any([seller, carrier, order_number, tracking_number, last_known_status]):
            return

        gmail_adapter = self.provider_registry.get_provider("gmail")
        existing_records = gmail_adapter.message_store.list_shipment_records(account_id)
        matched_record = None
        if tracking_number:
            matched_record = next(
                (
                    record
                    for record in existing_records
                    if self._action_decision_canonical_identifier(record.tracking_number) == tracking_number
                ),
                None,
            )
        if matched_record is None and order_number:
            matched_record = next(
                (
                    record
                    for record in existing_records
                    if self._action_decision_canonical_identifier(record.order_number) == order_number
                ),
                None,
            )
        if matched_record is None and message.message_id:
            matched_record = next((record for record in existing_records if record.record_id == f"msg:{message.message_id}"), None)

        if matched_record is not None:
            record = matched_record.model_copy(
                update={
                    "seller": seller or matched_record.seller,
                    "carrier": carrier or matched_record.carrier,
                    "order_number": order_number or matched_record.order_number,
                    "tracking_number": tracking_number or matched_record.tracking_number,
                    "domain": domain or matched_record.domain,
                    "last_known_status": last_known_status or matched_record.last_known_status,
                    "last_seen_at": message.received_at or matched_record.last_seen_at,
                    "status_updated_at": (
                        message.received_at if last_known_status and last_known_status != matched_record.last_known_status else matched_record.status_updated_at
                    ),
                }
            )
        else:
            record_id = (
                f"order:{order_number}"
                if order_number
                else f"tracking:{tracking_number}"
                if tracking_number
                else f"msg:{message.message_id}"
            )
            record = gmail_adapter.message_store.upsert_shipment_record(
                gmail_adapter.message_store.get_shipment_record(account_id, record_id)
                or GmailShipmentRecord(
                    account_id=account_id,
                    record_id=record_id,
                    seller=seller,
                    carrier=carrier,
                    order_number=order_number,
                    tracking_number=tracking_number,
                    domain=domain,
                    last_known_status=last_known_status,
                    last_seen_at=message.received_at,
                    status_updated_at=message.received_at if last_known_status else None,
                )
            )
            return
        gmail_adapter.message_store.upsert_shipment_record(record)

    async def _execute_email_action_decision_for_message(
        self,
        *,
        account_id: str,
        message,
        classification_label: GmailTrainingLabel,
        target_api_base_url: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, object] | None:
        if classification_label not in {GmailTrainingLabel.ACTION_REQUIRED, GmailTrainingLabel.ORDER}:
            return None
        if not self._runtime_ai_calls_enabled():
            AI_LOGGER.info(
                "Skipping AI action decision because AI calls are disabled",
                extra={"event_data": {"message_id": message.message_id}},
            )
            return None
        prompt_definition = self._load_runtime_prompt_definition("prompt.email.action_decision")
        prompt_runtime = prompt_definition.get("node_runtime")
        if not isinstance(prompt_runtime, dict) or not isinstance(prompt_runtime.get("json_schema"), dict):
            raise ValueError("prompt.email.action_decision is missing node_runtime.json_schema")
        if (
            not force_refresh
            and
            isinstance(message.action_decision_payload, dict)
            and message.action_decision_prompt_version == str(prompt_definition["version"])
        ):
            return message.action_decision_payload

        adapter = self.provider_registry.get_provider("gmail")
        full_message_text = None
        full_message_html = None
        full_message_payload = None
        try:
            full_message = await self.email_provider_gateway.gmail_fetch_full_message_text(account_id, message.message_id)
        except Exception as exc:
            AI_LOGGER.warning(
                "Full Gmail message fetch for action decision failed; using stored message fallback",
                extra={
                    "event_data": {
                        "message_id": message.message_id,
                        "detail": str(exc),
                    }
                },
            )
        else:
            if isinstance(full_message, dict):
                full_message_text = str(full_message.get("text_body") or "").strip() or None
                full_message_html = str(full_message.get("html_body") or "").strip() or None
                raw_payload = full_message.get("raw_payload")
                if isinstance(raw_payload, dict):
                    full_message_payload = raw_payload
        normalized_target_base_url = self._normalize_target_api_base_url(
            target_api_base_url or self._default_ai_runtime_target_api_base_url()
        )
        request_body = {
            "task_id": f"email-action-{uuid.uuid4().hex}",
            "prompt_id": str(prompt_definition["prompt_id"]),
            "prompt_version": str(prompt_definition["version"]),
            "task_family": str(prompt_definition.get("task_family") or "task.classification"),
            "requested_by": "node-email",
            "service_id": str(prompt_definition.get("service_id") or "node-email"),
            "customer_id": "local-user",
            "trace_id": f"trace-action-{uuid.uuid4().hex}",
            "inputs": {
                **self._build_action_decision_inputs(
                    account_id=account_id,
                    message=message,
                    full_message_text=full_message_text,
                    full_message_html=full_message_html,
                    full_message_payload=full_message_payload,
                ),
                "json_schema": prompt_runtime["json_schema"],
            },
            "timeout_s": int(prompt_runtime.get("timeout_s", 45)),
        }
        try:
            normalized_target_base_url, execution_payload = await self.ai_gateway.execute_direct(
                normalized_target_base_url,
                request_body=request_body,
            )
        except Exception as exc:
            error_message = self._runtime_execution_error_message(exc)
            AI_LOGGER.error(
                "AI action decision execution failed",
                extra={
                    "event_data": {
                        "target_api_base_url": normalized_target_base_url,
                        "message_id": message.message_id,
                        "detail": error_message,
                    }
                },
            )
            return None
        parsed_decision = self._parse_action_decision_output(
            execution_payload.get("output") if isinstance(execution_payload, dict) else None
        )
        validation_error = (
            "output could not be parsed into an action decision object"
            if not isinstance(parsed_decision, dict)
            else self._validate_json_schema_value(parsed_decision, prompt_runtime["json_schema"])
        )
        debug_payload = self._action_decision_debug_payload(
            prompt_version=str(prompt_definition["version"]),
            execution_payload=execution_payload,
            parsed_output=parsed_decision,
            validation_error=validation_error,
            target_api_base_url=normalized_target_base_url,
        )
        self.provider_registry.get_provider("gmail").message_store.update_action_decision_debug_response(
            account_id,
            message.message_id,
            raw_response=debug_payload,
        )
        if validation_error is not None:
            AI_LOGGER.warning(
                "AI action decision output rejected",
                extra={
                    "event_data": {
                        "message_id": message.message_id,
                        "detail": validation_error,
                    }
                },
            )
            return None
        decision = self._validate_action_decision_payload(parsed_decision, prompt_runtime["json_schema"])
        if not isinstance(decision, dict):
            return None
        self.provider_registry.get_provider("gmail").message_store.update_action_decision(
            account_id,
            message.message_id,
            payload=decision,
            prompt_version=str(prompt_definition["version"]),
        )
        self._upsert_tracked_order_from_action_decision(
            account_id=account_id,
            message=message,
            action_decision=decision,
        )
        return decision

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
        await self.background_tasks.startup()

    async def stop(self) -> None:
        await self.background_tasks.shutdown()
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
        self.onboarding.reset_onboarding_state()

    def _clear_trust_and_onboarding_state(self) -> None:
        self.onboarding.clear_trust_and_onboarding_state()

    def _normalize_core_base_url(self, value: str | None) -> str | None:
        return self.onboarding.normalize_core_base_url(value)

    def _normalize_selected_task_capabilities(self, values: list[str] | None) -> list[str]:
        return self.onboarding.normalize_selected_task_capabilities(values)

    def _capability_setup_summary(self, provider_overview: dict[str, object]) -> dict[str, object]:
        return self.governance.capability_setup_summary(provider_overview)

    def _resolve_advertised_host(self) -> str:
        return self.onboarding.resolve_advertised_host()

    def _advertised_api_base_url(self) -> str:
        return self.onboarding.advertised_api_base_url()

    def _advertised_ui_endpoint(self) -> str:
        return self.onboarding.advertised_ui_endpoint()

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
        return self.onboarding.normalize_platform_core_id(value)

    def _extract_hexe_core_uuid(self, value: str | None) -> str | None:
        return self.onboarding.extract_hexe_core_uuid(value)

    def _format_core_error(self, exc: httpx.HTTPError) -> str:
        return self.onboarding.format_core_error(exc)

    def _extract_core_error_message(self, response: httpx.Response) -> str | None:
        return self.onboarding.extract_core_error_message(response)

    def _ensure_polling(self) -> None:
        self.background_tasks.ensure_finalize_polling()

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
        self.notifications.connect_mqtt_if_possible()

    def _record_heartbeat(self) -> None:
        self.notifications.record_heartbeat()

    def _handle_notification_result(self, result: NodeNotificationResult) -> None:
        self.notifications.handle_notification_result(result)

    def _handle_mqtt_connected(self) -> None:
        self.notifications.handle_mqtt_connected()

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
        return self.notifications.send_user_notification(
            title=title,
            message=message,
            severity=severity,
            urgency=urgency,
            dedupe_key=dedupe_key,
            event_type=event_type,
            summary=summary,
            source_component=source_component,
            data=data,
        )

    def _set_gmail_fetch_notification_state(self, next_state: str, detail: str) -> None:
        self.notifications.set_gmail_fetch_notification_state(next_state, detail)

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
        action_decision: dict[str, object] | None = None,
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
        message_lines = self._render_email_notification_message_lines(
            classification_label=classification_label,
            sender_text=sender_text,
            subject_text=subject_text,
            confidence_text=confidence_text,
            sender_reputation_text=sender_reputation_text,
            action_decision=action_decision,
        )
        delivery_severity, delivery_urgency = self._email_notification_delivery_profile(
            classification_label=classification_label,
            action_decision=action_decision,
        )
        notification_title = self._email_notification_title(
            classification_label=classification_label,
            action_decision=action_decision,
        )
        notification_summary = self._email_notification_summary(
            classification_label=classification_label,
            action_decision=action_decision,
        )
        if sender_reputation_text and sender_reputation_text not in message_lines:
            message_lines.append(sender_reputation_text)
        return self.send_user_notification(
            title=notification_title,
            message="\n".join(message_lines),
            severity=delivery_severity,
            urgency=delivery_urgency,
            dedupe_key=f"gmail-classification-{classification_label.value}-{message_id}",
            event_type=spec["event_type"],
            summary=notification_summary,
            source_component=source_component,
            data={
                "message_id": message_id,
                "classification_label": classification_label.value,
                "sender": sender,
                "subject": subject,
                "confidence": confidence,
                "sender_reputation": sender_reputation,
                "action_decision": action_decision,
            },
        )

    def _email_notification_title(
        self,
        *,
        classification_label: GmailTrainingLabel,
        action_decision: dict[str, object] | None,
    ) -> str:
        return "Action Required email" if classification_label == GmailTrainingLabel.ACTION_REQUIRED else "Order email"

    def _email_notification_summary(
        self,
        *,
        classification_label: GmailTrainingLabel,
        action_decision: dict[str, object] | None,
    ) -> str:
        if not isinstance(action_decision, dict):
            return "New action-required email classified" if classification_label == GmailTrainingLabel.ACTION_REQUIRED else "New order email classified"
        summary = str(action_decision.get("summary") or "").strip()
        if summary:
            return summary
        return "New action-required email classified" if classification_label == GmailTrainingLabel.ACTION_REQUIRED else "New order email classified"

    @staticmethod
    def _format_action_name(action_name: str) -> str:
        return action_name.replace("_", " ").strip().title()

    def _email_notification_delivery_profile(
        self,
        *,
        classification_label: GmailTrainingLabel,
        action_decision: dict[str, object] | None,
    ) -> tuple[str, str]:
        severity = "warning" if classification_label == GmailTrainingLabel.ACTION_REQUIRED else "info"
        urgency = "actions_needed" if classification_label == GmailTrainingLabel.ACTION_REQUIRED else "notification"
        if not isinstance(action_decision, dict):
            return severity, urgency
        urgency_value = str(action_decision.get("urgency") or "").strip().lower()
        action_names = {
            str(item.get("action") or "").strip().lower()
            for item in action_decision.get("recommended_actions") or []
            if isinstance(item, dict)
        }
        if urgency_value in {"high", "urgent"} or "flag_time_sensitive" in action_names:
            severity = "warning"
            urgency = "actions_needed"
        if bool(action_decision.get("human_review_required")) or "human_review_required" in action_names:
            severity = "warning"
            urgency = "actions_needed"
        if "mark_priority" in action_names and severity == "info":
            severity = "warning"
        return severity, urgency

    def _render_email_notification_message_lines(
        self,
        *,
        classification_label: GmailTrainingLabel,
        sender_text: str,
        subject_text: str,
        confidence_text: str,
        sender_reputation_text: str | None,
        action_decision: dict[str, object] | None,
    ) -> list[str]:
        if not isinstance(action_decision, dict):
            lines = [
                f"From: {sender_text}",
                f"Subject: {subject_text}",
                f"Confidence: {confidence_text}",
            ]
            if sender_reputation_text:
                lines.append(sender_reputation_text)
            return lines

        lines = [
            f"From: {sender_text}",
            f"Subject: {subject_text}",
        ]
        summary = str(action_decision.get("summary") or "").strip()
        if summary:
            lines.append(f"Summary: {summary}")
        urgency_value = str(action_decision.get("urgency") or "").strip().lower()
        if urgency_value:
            lines.append(f"Urgency: {urgency_value}")
        recommended_actions = action_decision.get("recommended_actions")
        if isinstance(recommended_actions, list) and recommended_actions:
            lines.append("Recommended actions:")
            for item in recommended_actions:
                if not isinstance(item, dict):
                    continue
                action_name = str(item.get("action") or "").strip().lower()
                if not action_name:
                    continue
                reason = str(item.get("reason") or "").strip()
                action_confidence = self._normalize_classifier_confidence(item.get("confidence"))
                if reason and action_confidence is not None:
                    lines.append(f"- {self._format_action_name(action_name)} ({action_confidence:.2f}): {reason}")
                elif reason:
                    lines.append(f"- {self._format_action_name(action_name)}: {reason}")
                elif action_confidence is not None:
                    lines.append(f"- {self._format_action_name(action_name)} ({action_confidence:.2f})")
                else:
                    lines.append(f"- {self._format_action_name(action_name)}")
        tracking_signals = action_decision.get("tracking_signals")
        if isinstance(tracking_signals, dict) and bool(tracking_signals.get("is_shipment_related")):
            current_status = str(tracking_signals.get("current_status") or "").strip()
            seller = str(tracking_signals.get("seller") or "").strip()
            carrier = str(tracking_signals.get("carrier") or "").strip()
            order_number = str(tracking_signals.get("order_number") or "").strip()
            tracking_number = str(tracking_signals.get("tracking_number") or "").strip()
            tracking_parts = [part for part in [current_status, seller, carrier, order_number, tracking_number] if part]
            if tracking_parts:
                lines.append(f"Tracking: {' | '.join(tracking_parts)}")
        time_signals = action_decision.get("time_signals")
        if isinstance(time_signals, dict):
            deadline_mentions = time_signals.get("deadline_mentions")
            time_window_mentions = time_signals.get("time_window_mentions")
            deadline_text = ", ".join(str(item).strip() for item in deadline_mentions or [] if str(item).strip())
            time_window_text = ", ".join(str(item).strip() for item in time_window_mentions or [] if str(item).strip())
            if deadline_text:
                lines.append(f"Deadlines: {deadline_text}")
            if time_window_text:
                lines.append(f"Time windows: {time_window_text}")
        calendar_signals = action_decision.get("calendar_signals")
        if isinstance(calendar_signals, dict) and (
            bool(calendar_signals.get("has_calendar_invite")) or bool(calendar_signals.get("has_meeting_request"))
        ):
            time_mentions = calendar_signals.get("time_mentions")
            time_mentions_text = ", ".join(str(item).strip() for item in time_mentions or [] if str(item).strip())
            if time_mentions_text:
                lines.append(f"Calendar signals: {time_mentions_text}")
            else:
                lines.append("Calendar signals: meeting or invite detected")
        if bool(action_decision.get("human_review_required")):
            lines.append("Human review required: yes")
        if sender_reputation_text:
            lines.append(sender_reputation_text)
        lines.append(f"Classifier confidence: {confidence_text}")
        return lines

    async def _notify_for_new_email_classification(
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
        if classification_label == GmailTrainingLabel.ORDER:
            try:
                await self._run_order_phase1_flow(account_id=account_id, message=message)
            except Exception as exc:
                LOGGER.warning(
                    "ORDER Phase 1 flow failed during classification handling",
                    extra={
                        "event_data": {
                            "account_id": account_id,
                            "message_id": message_id,
                            "detail": str(exc),
                        }
                    },
                )
        sender_reputation = self._sender_reputation_context(account_id, sender=message.sender)
        action_decision = await self._execute_email_action_decision_for_message(
            account_id=account_id,
            message=message,
            classification_label=classification_label,
        )
        refreshed_message = adapter.message_store.get_message(account_id, message_id)
        if refreshed_message is not None:
            message = refreshed_message
        sent = self.send_email_classification_notification(
            classification_label=classification_label,
            sender=message.sender,
            subject=message.subject,
            confidence=confidence,
            sender_reputation=sender_reputation,
            message_id=message_id,
            source_component=source_component,
            action_decision=action_decision or message.action_decision_payload,
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

    async def _run_order_phase1_flow(self, *, account_id: str, message) -> None:
        adapter = self.provider_registry.get_provider("gmail")
        normalized = await self.gmail_order_flow.fetch_and_normalize_message(
            adapter=adapter,
            account_id=account_id,
            message_id=message.message_id,
        )
        LOGGER.info(
            "ORDER Phase 1 normalization completed",
            extra={
                "event_data": {
                    "account_id": account_id,
                    "message_id": message.message_id,
                    "fetch_status": normalized.fetch_status,
                    "decode_status": normalized.decode_state.status,
                    "selected_body_type": normalized.selected_body_type,
                }
            },
        )

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
        return await self.runtime_sync_prompts(
            RuntimePromptSyncRequestInput(target_api_base_url=payload.target_api_base_url),
            correlation_id=correlation_id,
        )

    async def runtime_sync_prompts(
        self,
        payload: RuntimePromptSyncRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        if not self._runtime_ai_calls_enabled():
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            self._save_runtime_task_state(
                request_status="failed",
                last_step="register",
                detail=self._runtime_ai_disabled_message(),
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload={
                    "target_api_base_url": self._normalize_target_api_base_url(payload.target_api_base_url),
                    "review_due_migration": bool(payload.review_due_migration),
                },
                execution_response=None,
                usage_summary_response=current.get("usage_summary_response"),
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
            raise ValueError(self._runtime_ai_disabled_message())
        return await self._sync_runtime_prompts(
            target_api_base_url=payload.target_api_base_url,
            review_due_migration=payload.review_due_migration,
            correlation_id=correlation_id,
            persist_runtime_state=True,
            sync_reason="manual",
        )

    async def runtime_review_prompt(
        self,
        payload: RuntimePromptReviewRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        if not self._runtime_ai_calls_enabled():
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            self._save_runtime_task_state(
                request_status="failed",
                last_step="review",
                detail=self._runtime_ai_disabled_message(),
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload={
                    "target_api_base_url": self._normalize_target_api_base_url(payload.target_api_base_url),
                    "prompt_id": payload.prompt_id,
                    "review_status": payload.review_status,
                },
                execution_response=None,
                usage_summary_response=current.get("usage_summary_response"),
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
            raise ValueError(self._runtime_ai_disabled_message())
        normalized_target_base_url = self._normalize_target_api_base_url(payload.target_api_base_url)
        result = await self._review_remote_prompt_service(
            normalized_target_base_url,
            prompt_id=payload.prompt_id,
            review_status=payload.review_status,
            reason=payload.reason,
        )
        return {
            "ok": True,
            "task_id": f"runtime-{uuid.uuid4().hex}",
            "trace_id": correlation_id or f"runtime-{uuid.uuid4().hex}",
            "target_api_base_url": normalized_target_base_url,
            "review_result": result,
        }

    async def update_runtime_task_settings(self, payload: RuntimeTaskSettingsInput) -> dict[str, object]:
        current = self._runtime_task_state()
        state = self._save_runtime_task_state(
            ai_calls_enabled=(
                current.get("ai_calls_enabled")
                if payload.ai_calls_enabled is None
                else bool(payload.ai_calls_enabled)
            ),
            provider_calls_enabled=(
                current.get("provider_calls_enabled")
                if payload.provider_calls_enabled is None
                else bool(payload.provider_calls_enabled)
            ),
        )
        return {
            "ok": True,
            "runtime_task_state": state,
        }

    def _prompt_definition_dir(self) -> Path:
        return self.runtime.prompt_definition_dir()

    def _load_runtime_prompt_definitions(self) -> list[dict[str, object]]:
        return self.runtime.load_runtime_prompt_definitions()

    def _load_runtime_prompt_definition(self, prompt_id: str) -> dict[str, object]:
        return self.runtime.load_runtime_prompt_definition(prompt_id)

    @staticmethod
    def _prompt_registration_payload(prompt_definition: dict[str, object]) -> dict[str, object]:
        return RuntimeManager.prompt_registration_payload(prompt_definition)

    @staticmethod
    def _normalize_target_api_base_url(target_api_base_url: str | None) -> str:
        return RuntimeManager.normalize_target_api_base_url(target_api_base_url)

    async def _list_remote_prompt_services(self, target_api_base_url: str) -> list[dict[str, object]]:
        return await self.ai_gateway.list_prompt_services(target_api_base_url)

    async def _get_remote_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
    ) -> dict[str, object] | None:
        return await self.ai_gateway.get_prompt_service(target_api_base_url, prompt_id=prompt_id)

    async def _register_prompt_service(
        self,
        target_api_base_url: str,
        prompt_definition: dict[str, object],
    ) -> dict[str, object]:
        request_body = self._prompt_registration_payload(prompt_definition)
        return await self.ai_gateway.register_prompt_service(target_api_base_url, request_body)

    async def _update_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
        prompt_definition: dict[str, object],
    ) -> dict[str, object]:
        request_body = self.runtime.prompt_update_payload(prompt_definition)
        return await self.ai_gateway.update_prompt_service(
            target_api_base_url,
            prompt_id=prompt_id,
            request_body=request_body,
        )

    async def _retire_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
        reason: str,
    ) -> dict[str, object]:
        return await self.ai_gateway.retire_prompt_service(
            target_api_base_url,
            prompt_id=prompt_id,
            reason=reason,
        )

    async def _review_remote_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
        review_status: str,
        reason: str | None,
    ) -> dict[str, object]:
        return await self.ai_gateway.review_prompt_service(
            target_api_base_url,
            prompt_id=prompt_id,
            review_status=review_status,
            reason=reason,
        )

    async def _migrate_remote_prompts_to_review_due(self, target_api_base_url: str) -> dict[str, object]:
        return await self.ai_gateway.migrate_prompts_to_review_due(target_api_base_url)

    @staticmethod
    def _runtime_prompt_remote_status(remote_record: dict[str, object] | None) -> str | None:
        if not isinstance(remote_record, dict):
            return None
        status = remote_record.get("status")
        return str(status).strip() or None if status is not None else None

    @staticmethod
    def _runtime_prompt_remote_version(remote_record: dict[str, object] | None) -> str | None:
        if not isinstance(remote_record, dict):
            return None
        version = remote_record.get("current_version")
        return str(version).strip() or None if version is not None else None

    @classmethod
    def _prompt_update_required(
        cls,
        *,
        local_version: str,
        remote_version: str | None,
        remote_status: str | None,
    ) -> bool:
        if remote_version != local_version:
            return True
        if remote_status in {None, "", "retired"}:
            return True
        return False

    @staticmethod
    def _runtime_execution_error_message(exc: Exception) -> str:
        message = str(exc)
        if not isinstance(exc, httpx.HTTPStatusError) or exc.response is None:
            return message
        try:
            payload = exc.response.json()
        except Exception:
            return message
        if not isinstance(payload, dict):
            return message
        detail = payload.get("detail")
        if isinstance(detail, dict):
            lifecycle_state = detail.get("lifecycle_state") or detail.get("status")
            denial_reason = detail.get("reason") or detail.get("message") or detail.get("detail")
            if lifecycle_state:
                if lifecycle_state == "review_due":
                    return (
                        "Remote prompt is in review_due state but should remain executable; "
                        f"remote node denied execution: {denial_reason or 'no reason provided'}"
                    )
                return f"Remote prompt execution denied by lifecycle state {lifecycle_state}: {denial_reason or 'no reason provided'}"
            if denial_reason:
                return str(denial_reason)
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        message_text = payload.get("message")
        if isinstance(message_text, str) and message_text.strip():
            return message_text.strip()
        return message

    async def _sync_runtime_prompts(
        self,
        *,
        target_api_base_url: str | None,
        review_due_migration: bool,
        correlation_id: str | None,
        persist_runtime_state: bool,
        sync_reason: str,
    ) -> dict[str, object]:
        normalized_target_base_url = self._normalize_target_api_base_url(target_api_base_url)
        task_id = f"runtime-{uuid.uuid4().hex}"
        prompt_definitions = self._load_runtime_prompt_definitions()
        remote_prompt_services: list[dict[str, object]] = []
        registrations: list[dict[str, object]] = []
        updates: list[dict[str, object]] = []
        retirements: list[dict[str, object]] = []
        sync_actions: list[dict[str, object]] = []
        review_due_migration_result: dict[str, object] | None = None
        registration_payloads = [self._prompt_registration_payload(item) for item in prompt_definitions]

        try:
            if review_due_migration:
                review_due_migration_result = await self._migrate_remote_prompts_to_review_due(normalized_target_base_url)
            remote_prompt_services = await self._list_remote_prompt_services(normalized_target_base_url)
            for prompt_definition in prompt_definitions:
                prompt_id = str(prompt_definition["prompt_id"])
                local_version = str(prompt_definition["version"])
                remote_record = await self._get_remote_prompt_service(
                    normalized_target_base_url,
                    prompt_id=prompt_id,
                )
                remote_version = self._runtime_prompt_remote_version(remote_record)
                remote_status = self._runtime_prompt_remote_status(remote_record)
                if remote_record is None:
                    registration = await self._register_prompt_service(normalized_target_base_url, prompt_definition)
                    registrations.append(registration)
                    sync_actions.append(
                        {
                            "prompt_id": prompt_id,
                            "action": "registered",
                            "version": local_version,
                            "remote_version": None,
                            "remote_status": None,
                        }
                    )
                    continue
                if not self._prompt_update_required(
                    local_version=local_version,
                    remote_version=remote_version,
                    remote_status=remote_status,
                ):
                    sync_actions.append(
                        {
                            "prompt_id": prompt_id,
                            "action": "unchanged",
                            "version": local_version,
                            "remote_version": remote_version,
                            "remote_status": remote_status,
                        }
                    )
                    continue
                update_result = await self._update_prompt_service(
                    normalized_target_base_url,
                    prompt_id=prompt_id,
                    prompt_definition=prompt_definition,
                )
                updates.append(update_result)
                sync_actions.append(
                    {
                        "prompt_id": prompt_id,
                        "action": "updated",
                        "version": local_version,
                        "remote_version": remote_version,
                        "remote_status": remote_status,
                    }
                )
        except Exception as exc:
            response_payload: dict[str, object] | None = None
            message = str(exc)
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                try:
                    response_body = exc.response.json()
                except Exception:
                    response_body = exc.response.text
                response_payload = {"status_code": exc.response.status_code, "body": response_body}
                message = f"{message}: {response_body}"
            if persist_runtime_state:
                now = datetime.now(UTC).isoformat()
                current = self._runtime_task_state()
                self._save_runtime_task_state(
                    request_status="failed",
                    last_step="register",
                    detail=message,
                    preview_response=current.get("preview_response"),
                    resolve_response=current.get("resolve_response"),
                    authorize_response=current.get("authorize_response"),
                    registration_request_payload={"prompts": registration_payloads},
                    execution_response=response_payload,
                    usage_summary_response=None,
                    started_at=current.get("started_at") or now,
                    updated_at=now,
                )
                if review_due_migration:
                    self.state.runtime_prompt_review_due_migration_last_run_at = datetime.now().astimezone()
                    self.state.runtime_prompt_review_due_migration_target_api_base_url = normalized_target_base_url
                    self.state.runtime_prompt_review_due_migration_result = response_payload or {"message": message}
                    self.state_store.save(self.state)
            error = ValueError(message)
            error.detail = {
                "message": message,
                "request_payload": {"prompts": registration_payloads},
                "response_payload": response_payload,
            }
            raise error from exc

        if sync_reason == "manual":
            self.state.runtime_prompt_sync_target_api_base_url = normalized_target_base_url
            self.state.runtime_prompt_sync_weekly_slot_key = self._prompt_sync_weekly_slot_key(datetime.now().astimezone())
            if review_due_migration:
                self.state.runtime_prompt_review_due_migration_last_run_at = datetime.now().astimezone()
                self.state.runtime_prompt_review_due_migration_target_api_base_url = normalized_target_base_url
                self.state.runtime_prompt_review_due_migration_result = review_due_migration_result or {}
            self.state_store.save(self.state)
        result = {
            "ok": True,
            "task_id": task_id,
            "trace_id": correlation_id or task_id,
            "target_api_base_url": normalized_target_base_url,
            "request_payload": {"prompts": registration_payloads},
            "remote_prompt_services": remote_prompt_services,
            "registrations": registrations,
            "updates": updates,
            "retirements": retirements,
            "sync_actions": sync_actions,
            "review_due_migration_result": review_due_migration_result,
            "usage_summary": None,
        }
        if persist_runtime_state:
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            registered_count = sum(1 for item in sync_actions if item.get("action") == "registered")
            updated_count = sum(1 for item in sync_actions if item.get("action") == "updated")
            unchanged_count = sum(1 for item in sync_actions if item.get("action") == "unchanged")
            self._save_runtime_task_state(
                request_status="registered",
                last_step="register",
                detail=(
                    f"Prompt sync completed: {registered_count} registered, "
                    f"{updated_count} updated, {unchanged_count} unchanged."
                ),
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=result["request_payload"],
                execution_response={
                    "registrations": registrations,
                    "updates": updates,
                    "retirements": retirements,
                    "sync_actions": sync_actions,
                    "review_due_migration_result": review_due_migration_result,
                },
                usage_summary_response=None,
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
        return result

    @staticmethod
    def _prompt_sync_weekly_slot_key(now: datetime) -> str:
        return RuntimeManager.prompt_sync_weekly_slot_key(now)

    @staticmethod
    def _runtime_monthly_authorize_slot_key(now: datetime) -> str | None:
        return RuntimeManager.runtime_monthly_authorize_slot_key(now)

    async def _run_weekly_prompt_sync_if_due(self) -> None:
        target_api_base_url = self.state.runtime_prompt_sync_target_api_base_url
        if not target_api_base_url:
            return
        if not self._runtime_ai_calls_enabled():
            LOGGER.info("Scheduled weekly prompt sync skipped because AI calls are disabled")
            return
        now = datetime.now().astimezone()
        slot_key = self._prompt_sync_weekly_slot_key(now)
        if self.state.runtime_prompt_sync_weekly_slot_key == slot_key:
            return
        await self._sync_runtime_prompts(
            target_api_base_url=target_api_base_url,
            review_due_migration=False,
            correlation_id=None,
            persist_runtime_state=False,
            sync_reason="weekly",
        )
        self.state.runtime_prompt_sync_weekly_slot_key = slot_key
        self.state.runtime_prompt_sync_last_scheduled_at = datetime.now().astimezone()
        self.state_store.save(self.state)

    async def _run_due_monthly_runtime_authorize(self, now: datetime) -> None:
        slot_key = self._runtime_monthly_authorize_slot_key(now)
        if slot_key is None or self.state.runtime_monthly_authorize_slot_key == slot_key:
            return
        if self.state.trust_state != "trusted" or not self.state.node_id or not self.effective_core_base_url():
            return
        try:
            LOGGER.info(
                "Scheduled monthly Core resolve and authorize starting",
                extra={"event_data": {"slot_key": slot_key}},
            )
            resolve_response = await self.core_service_resolve(
                CoreServiceResolveRequestInput(
                    task_family="task.classification",
                    type="ai",
                    task_context={"content_type": "email"},
                    preferred_provider="openai",
                )
            )
            selected_service_id = str(
                resolve_response.get("selected_service_id")
                or resolve_response.get("service_id")
                or ""
            ).strip()
            candidates = resolve_response.get("candidates")
            selected_candidate = candidates[0] if isinstance(candidates, list) and candidates else {}
            provider = str(
                resolve_response.get("provider")
                or (selected_candidate.get("provider") if isinstance(selected_candidate, dict) else None)
                or "openai"
            ).strip()
            model_id_value = (
                resolve_response.get("model_id")
                or (selected_candidate.get("models_allowed", [None])[0] if isinstance(selected_candidate, dict) else None)
            )
            model_id = str(model_id_value).strip() if model_id_value else None
            if not selected_service_id:
                raise ValueError("Core resolve did not return a service_id")
            await self.core_service_authorize(
                CoreServiceAuthorizeRequestInput(
                    task_family="task.classification",
                    type="ai",
                    task_context={"content_type": "email"},
                    service_id=selected_service_id,
                    provider=provider or "openai",
                    model_id=model_id,
                )
            )
            self.state.runtime_monthly_authorize_slot_key = slot_key
            self.state.runtime_monthly_authorize_last_run_at = datetime.now().astimezone()
            self.state_store.save(self.state)
            LOGGER.info(
                "Scheduled monthly Core resolve and authorize completed",
                extra={"event_data": {"slot_key": slot_key, "service_id": selected_service_id}},
            )
        except Exception as exc:
            LOGGER.error(
                "Scheduled monthly Core resolve and authorize failed",
                extra={"event_data": {"slot_key": slot_key, "detail": str(exc)}},
            )

    async def runtime_execute_email_classifier(
        self,
        payload: RuntimePromptExecutionRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        if not self._runtime_ai_calls_enabled():
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            self._save_runtime_task_state(
                request_status="failed",
                last_step="execute",
                detail=self._runtime_ai_disabled_message(),
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=current.get("registration_request_payload"),
                execution_request_payload={"mode": "classifier_single"},
                execution_response=None,
                usage_summary_response=current.get("usage_summary_response"),
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
            raise ValueError(self._runtime_ai_disabled_message())
        adapter = self.provider_registry.get_provider("gmail")
        account_id = "primary"
        message = None
        if payload.message_id:
            message = adapter.message_store.get_message(account_id, payload.message_id)
            if message is None:
                raise ValueError(f"Gmail message {payload.message_id} was not found")
            if message.local_label and message.local_label != GmailTrainingLabel.UNKNOWN.value:
                raise ValueError(f"Gmail message {payload.message_id} is already labeled {message.local_label}")
        else:
            message = adapter.message_store.get_newest_unknown_message(account_id)
            if message is None:
                raise ValueError("no newest unknown Gmail message is available")
        return await self._execute_email_classifier_for_message(
            account_id=account_id,
            message=message,
            target_api_base_url=payload.target_api_base_url,
            correlation_id=correlation_id,
            persist_runtime_state=True,
        )

    async def runtime_execute_latest_email_action_decision(
        self,
        payload: RuntimePromptExecutionRequestInput,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        if not self._runtime_ai_calls_enabled():
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            self._save_runtime_task_state(
                request_status="failed",
                last_step="execute",
                detail=self._runtime_ai_disabled_message(),
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=current.get("registration_request_payload"),
                execution_request_payload={"mode": "action_decision_latest"},
                execution_response=None,
                usage_summary_response=current.get("usage_summary_response"),
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
            raise ValueError(self._runtime_ai_disabled_message())
        del correlation_id
        adapter = self.provider_registry.get_provider("gmail")
        account_id = "primary"
        if payload.message_id:
            message = adapter.message_store.get_message(account_id, payload.message_id)
            if message is None:
                raise ValueError(f"Gmail message {payload.message_id} was not found")
            if not message.local_label:
                raise ValueError(f"Gmail message {payload.message_id} does not have a classification label")
        else:
            message = adapter.message_store.get_newest_message_by_labels(
                account_id,
                labels=[GmailTrainingLabel.ACTION_REQUIRED, GmailTrainingLabel.ORDER],
            )
            if message is None:
                raise ValueError("no action_required or order Gmail message is available")
        if not message.local_label:
            raise ValueError("latest Gmail message does not have a classification label")
        classification_label = GmailTrainingLabel(str(message.local_label))
        if classification_label not in {GmailTrainingLabel.ACTION_REQUIRED, GmailTrainingLabel.ORDER}:
            raise ValueError(
                f"Gmail message {message.message_id} has unsupported classification {classification_label.value} for action decision"
            )
        action_decision = await self._execute_email_action_decision_for_message(
            account_id=account_id,
            message=message,
            classification_label=classification_label,
            target_api_base_url=payload.target_api_base_url,
            force_refresh=True,
        )
        if action_decision is None:
            refreshed_message = adapter.message_store.get_message(account_id, message.message_id)
            raw_debug = refreshed_message.action_decision_raw_response if refreshed_message is not None else None
            now = datetime.now(UTC).isoformat()
            current = self._runtime_task_state()
            self._save_runtime_task_state(
                request_status="failed",
                last_step="execute",
                detail=f"AI action decision request did not return a usable result for {message.message_id}.",
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=current.get("registration_request_payload"),
                execution_request_payload={"mode": "action_decision", "message_id": message.message_id},
                execution_response={
                    "status": "failed",
                    "message_id": message.message_id,
                    "classification_label": classification_label.value,
                    "raw_debug_response": raw_debug,
                    "completed_at": now,
                },
                usage_summary_response=current.get("usage_summary_response"),
                started_at=current.get("started_at") or now,
                updated_at=now,
            )
            raise ValueError("AI action decision request did not return a usable result")
        now = datetime.now(UTC).isoformat()
        current = self._runtime_task_state()
        result = {
            "status": "completed",
            "message_id": message.message_id,
            "classification_label": classification_label.value,
            "action_decision": action_decision,
            "completed_at": now,
        }
        self._save_runtime_task_state(
            request_status="executed",
            last_step="execute",
            detail=(
                f"Latest {classification_label.value} Gmail message sent to AI action decision and completed for {message.message_id}."
            ),
            preview_response=current.get("preview_response"),
            resolve_response=current.get("resolve_response"),
            authorize_response=current.get("authorize_response"),
            registration_request_payload=current.get("registration_request_payload"),
            execution_request_payload={"mode": "action_decision", "message_id": message.message_id},
            execution_response=result,
            usage_summary_response=None,
            started_at=current.get("started_at") or now,
            updated_at=now,
        )
        return result

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

        local_processed, ai_candidates = await self._classify_candidates_locally(account_id=account_id, candidates=candidates)
        local_classified = max(local_processed - len(ai_candidates), 0)
        if local_processed > 0 and hasattr(adapter, "refresh_sender_reputations"):
            await adapter.refresh_sender_reputations(account_id)
        ai_total = len(ai_candidates)
        ai_calls_enabled = self._runtime_ai_calls_enabled()
        if not ai_calls_enabled:
            final_result = {
                "ok": True,
                "batch_size": len(candidates),
                "local_processed": local_processed,
                "local_classified": local_classified,
                "ai_total": ai_total,
                "ai_attempted": 0,
                "ai_completed": 0,
                "ai_failed": 0,
                "ai_results": [],
                "ai_calls_enabled": False,
            }
            self._save_runtime_task_state(
                request_status="executed",
                last_step="execute_batch",
                detail=(
                    f"Runtime batch classification completed with AI calls disabled. "
                    f"Local classified {local_classified} emails successfully and skipped {ai_total} AI candidates."
                ),
                preview_response=current.get("preview_response"),
                resolve_response=current.get("resolve_response"),
                authorize_response=current.get("authorize_response"),
                registration_request_payload=current.get("registration_request_payload"),
                execution_request_payload=None,
                execution_response=final_result,
                usage_summary_response=None,
                started_at=current.get("started_at") or started_at,
                updated_at=datetime.now(UTC).isoformat(),
            )
            self._send_runtime_batch_classification_summary_notification(
                batch_size=len(candidates),
                local_classified=local_classified,
                ai_completed=0,
                ai_attempted=0,
            )
            return final_result
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

    async def _classify_candidates_locally(self, *, account_id: str, candidates: list) -> tuple[int, list]:
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
            await self._notify_for_new_email_classification(
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
        if not self._runtime_ai_calls_enabled():
            raise ValueError(self._runtime_ai_disabled_message())
        normalized_target_base_url = self._normalize_target_api_base_url(target_api_base_url)
        adapter = self.provider_registry.get_provider("gmail")
        account_record = adapter.account_store.load_account(account_id)
        my_addresses = [account_record.email_address] if account_record is not None and account_record.email_address else []
        sender_reputation = self._sender_reputation_context(account_id, sender=message.sender)
        normalized_text = self._build_ai_classifier_input_text(
            message,
            my_addresses=my_addresses,
            sender_reputation=sender_reputation,
        )
        prompt_definition = self._load_runtime_prompt_definition("prompt.email.classifier")
        prompt_runtime = prompt_definition.get("node_runtime")
        if not isinstance(prompt_runtime, dict) or not isinstance(prompt_runtime.get("json_schema"), dict):
            raise ValueError("prompt.email.classifier is missing node_runtime.json_schema")

        task_id = self._next_email_classify_task_id()
        trace_id = correlation_id or f"trace-email-{uuid.uuid4().hex}"
        request_body = {
            "task_id": task_id,
            "prompt_id": str(prompt_definition["prompt_id"]),
            "prompt_version": str(prompt_definition["version"]),
            "task_family": "task.classification",
            "requested_by": "node-email",
            "service_id": "node-email",
            "customer_id": "local-user",
            "trace_id": trace_id,
            "inputs": {
                "text": normalized_text,
                "json_schema": prompt_runtime["json_schema"],
            },
            "timeout_s": int(prompt_runtime.get("timeout_s", 60)),
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
            normalized_target_base_url, execution_payload = await self.ai_gateway.execute_direct(
                normalized_target_base_url,
                request_body=request_body,
            )
        except Exception as exc:
            error_message = self._runtime_execution_error_message(exc)
            AI_LOGGER.error(
                "AI classifier execution failed",
                extra={
                    "event_data": {
                        "target_api_base_url": normalized_target_base_url,
                        "message_id": message.message_id,
                        "task_id": task_id,
                        "detail": error_message,
                    }
                },
            )
            raise ValueError(error_message) from exc

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
                await self._notify_for_new_email_classification(
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
            scheduled_tasks=self._scheduled_tasks_snapshot(),
            scheduled_task_legend=self._scheduled_task_legend(),
            tracked_orders=self._tracked_orders_snapshot(),
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
            account_record = await self.email_provider_gateway.gmail_complete_oauth_callback(
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
        return await self.providers.gmail_accounts_status()

    async def gmail_account_status(self, account_id: str) -> dict[str, object]:
        return await self.providers.gmail_account_status(account_id)

    async def gmail_status(self) -> dict[str, object]:
        return await self.providers.gmail_status()

    async def gmail_fetch_messages(
        self,
        window: str,
        *,
        account_id: str = "primary",
        reason: str = "manual",
        slot_key: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        return await self.providers.gmail_fetch_messages(
            window,
            account_id=account_id,
            reason=reason,
            slot_key=slot_key,
            correlation_id=correlation_id,
        )

    async def _run_last_hour_pipeline(
        self,
        *,
        account_id: str,
        mode: str,
        fetched_count: int,
        correlation_id: str | None,
    ) -> dict[str, object]:
        return await self.providers.run_last_hour_pipeline(
            account_id=account_id,
            mode=mode,
            fetched_count=fetched_count,
            correlation_id=correlation_id,
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
                await self._notify_for_new_email_classification(
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
                await self._notify_for_new_email_classification(
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
        return await self.providers.provider_status_snapshot_async()

    async def _refresh_post_trust_state(self) -> None:
        await self.governance.refresh_post_trust_state()

    def _ensure_gmail_status_polling(self) -> None:
        self.background_tasks.ensure_gmail_status_polling()

    def _ensure_gmail_fetch_polling(self) -> None:
        self.background_tasks.ensure_gmail_fetch_polling()

    async def _gmail_status_loop(self) -> None:
        await self.background_tasks.gmail_status_loop()

    async def _refresh_gmail_status(self) -> None:
        await self.background_tasks.refresh_gmail_status()

    async def _gmail_fetch_loop(self) -> None:
        await self.background_tasks.gmail_fetch_loop()

    async def _run_due_gmail_fetches(self) -> None:
        await self.background_tasks.run_due_gmail_fetches()

    def _due_gmail_fetch_windows(self, now: datetime, schedule_state) -> list[tuple[str, str]]:
        return self.background_tasks.due_gmail_fetch_windows(now, schedule_state)

    async def _run_due_hourly_batch_classification(self, now: datetime) -> None:
        await self.background_tasks.run_due_hourly_batch_classification(now)

    def _gmail_hourly_batch_slot_key(self, now: datetime) -> str | None:
        return BackgroundTaskManager.gmail_hourly_batch_slot_key(now)

    def _gmail_fetch_slot_key(self, window: str, now: datetime) -> str | None:
        return BackgroundTaskManager.gmail_fetch_slot_key(window, now)

    def _seconds_until_next_minute(self) -> float:
        return BackgroundTaskManager.seconds_until_next_minute()

    async def declare_selected_capabilities(self) -> StatusResponse:
        return await self.governance.declare_selected_capabilities()

    async def redeclare_capabilities(self, *, force: bool = False) -> StatusResponse:
        return await self.governance.redeclare_capabilities(force=force)

    async def rebuild_capabilities(self, *, force: bool = False) -> dict[str, object]:
        return await self.governance.rebuild_capabilities(force=force)

    async def _declare_capabilities(self, overview: dict[str, object] | None = None) -> CapabilityDeclarationResult:
        return await self.governance.declare_capabilities(overview)

    async def _sync_governance(self) -> GovernanceSnapshot:
        return await self.governance.sync_governance()

    async def _update_operational_readiness(self) -> None:
        await self.governance.update_operational_readiness()
