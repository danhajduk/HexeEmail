from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def to_report_data(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: to_report_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_report_data(item) for item in value]
    return value


class SharedFlowReportBuilder:
    def build_payload(
        self,
        *,
        ran_at: str,
        label: str,
        account_id: str,
        message_id: str,
        normalized,
        flow_result: dict[str, object],
    ) -> dict[str, object]:
        phase7_result = flow_result.get("phase7_result") or {}
        action_results = {
            "action_gate": to_report_data(flow_result.get("action_gate")),
            "action_router": to_report_data(flow_result.get("action_router")),
            "order_record_write": to_report_data(flow_result.get("order_record_write")),
            "user_notification": to_report_data(flow_result.get("user_notification")),
            "tracking_monitor": to_report_data(flow_result.get("tracking_monitor")),
        }
        payload = {
            "ran_at": ran_at,
            "label": label,
            "account_id": account_id,
            "message_id": message_id,
            "flow_family": str(flow_result.get("flow_family") or "unknown"),
            "output_schema_family": getattr(flow_result.get("flow_config"), "output_schema_family", None),
            "phase1": to_report_data(normalized),
            "phase2": to_report_data(flow_result.get("phase2")),
            "phase3": to_report_data(flow_result.get("phase3")),
            "phase4": to_report_data(flow_result.get("phase4")),
            "phase6": to_report_data(flow_result.get("phase6")),
            "phase7": to_report_data(flow_result.get("phase7")),
            "phase7_result": to_report_data(phase7_result),
            **action_results,
        }
        payload["report_summary"] = self.build_summary(payload)
        return payload

    def build_summary(self, payload: dict[str, object]) -> dict[str, object]:
        phase1 = payload.get("phase1") or {}
        phase2 = payload.get("phase2") or {}
        phase3 = payload.get("phase3") or {}
        phase4 = payload.get("phase4") or {}
        phase6 = payload.get("phase6") or {}
        phase7 = payload.get("phase7") or {}
        action_gate = payload.get("action_gate") or {}
        action_router = payload.get("action_router") or {}

        return {
            "status": {
                "phase1": phase1.get("fetch_status"),
                "phase2": phase2.get("scrub_status"),
                "phase3": phase3.get("profile_status"),
                "phase4": phase4.get("extraction_status"),
                "phase6": phase6.get("decision"),
                "phase7": self.render_phase7_status(phase7),
            },
            "diagnostics": {
                "phase4_template": list(phase4.get("template_diagnostics") or []),
                "phase4_field": list(phase4.get("field_diagnostics") or []),
                "phase7": list(phase7.get("diagnostics") or []),
                "action_gate": list(action_gate.get("diagnostics") or []),
                "action_router": list(action_router.get("diagnostics") or []),
            },
            "decision": to_report_data(phase6),
            "persistence": to_report_data(phase7),
            "actions": {
                "gate": to_report_data(action_gate),
                "router": to_report_data(action_router),
                "results": {
                    "order_record_write": to_report_data(payload.get("order_record_write")),
                    "user_notification": to_report_data(payload.get("user_notification")),
                    "tracking_monitor": to_report_data(payload.get("tracking_monitor")),
                },
            },
        }

    def build_markdown(self, payload: dict[str, object]) -> str:
        phase1_payload = payload.get("phase1") or {}
        phase2_payload = payload.get("phase2") or {}
        phase3_payload = payload.get("phase3") or {}
        phase4_payload = payload.get("phase4") or {}
        phase6_payload = payload.get("phase6") or {}
        phase7_payload = payload.get("phase7") or {}
        lines = [
            f"# {str(payload.get('flow_family') or 'flow').upper()} Flow Report: {payload.get('message_id')}",
            "",
            f"- Label: `{payload.get('label')}`",
            f"- Account: `{payload.get('account_id')}`",
            f"- Ran at: `{payload.get('ran_at')}`",
            f"- Flow family: `{payload.get('flow_family')}`",
            f"- Output schema family: `{payload.get('output_schema_family')}`",
            f"- Subject: `{phase1_payload.get('subject')}`",
            f"- Sender: `{phase1_payload.get('sender_email') or phase1_payload.get('sender')}`",
            "",
            "## Status",
            f"- Phase 1: `{phase1_payload.get('fetch_status')}`",
            f"- Phase 2: `{phase2_payload.get('scrub_status')}`",
            f"- Phase 3: `{phase3_payload.get('profile_status')}` / profile `{phase3_payload.get('profile_id')}` / confidence `{phase3_payload.get('profile_confidence')}` `{phase3_payload.get('profile_confidence_level')}`",
            f"- Phase 4: `{phase4_payload.get('extraction_status')}` / template `{phase4_payload.get('template_id')}` / extraction confidence `{phase4_payload.get('extraction_confidence')}` `{phase4_payload.get('extraction_confidence_level')}`",
            f"- Phase 6: `{phase6_payload.get('decision')}`",
            f"- Phase 7: `{self.render_phase7_status(phase7_payload)}`",
            "",
            "## Diagnostics",
        ]
        for item in phase4_payload.get("template_diagnostics") or []:
            lines.append(f"- `{item}`")
        lines.extend(
            [
                "",
                "## Phase 7",
                f"- Persisted: `{phase7_payload.get('persisted')}`",
                f"- Trust level: `{phase7_payload.get('trust_level')}`",
                f"- Blocked reason: `{phase7_payload.get('blocked_reason')}`",
                f"- Record path: `{phase7_payload.get('record_path')}`",
                "",
                "## Actions",
                f"- Action gate allowed: `{(payload.get('action_gate') or {}).get('actions_allowed')}`",
                f"- Action intents: `{(payload.get('action_router') or {}).get('action_intents')}`",
                f"- Order record write queued: `{(payload.get('order_record_write') or {}).get('queued')}`",
                f"- User notification queued: `{(payload.get('user_notification') or {}).get('queued')}`",
                f"- Tracking monitor queued: `{(payload.get('tracking_monitor') or {}).get('queued')}`",
            ]
        )
        return "\n".join(lines) + "\n"

    def build_index_entry(self, *, payload: dict[str, object], json_path: Path, markdown_path: Path) -> dict[str, object]:
        phase3_payload = payload.get("phase3") or {}
        phase4_payload = payload.get("phase4") or {}
        phase6_payload = payload.get("phase6") or {}
        phase7_payload = payload.get("phase7") or {}
        return {
            "message_id": payload.get("message_id"),
            "label": payload.get("label"),
            "ran_at": payload.get("ran_at"),
            "flow_family": payload.get("flow_family"),
            "json_report": str(json_path),
            "markdown_report": str(markdown_path),
            "phase3_profile": phase3_payload.get("profile_id"),
            "phase3_confidence": phase3_payload.get("profile_confidence"),
            "phase4_status": phase4_payload.get("extraction_status"),
            "phase4_template_id": phase4_payload.get("template_id"),
            "phase6_decision": phase6_payload.get("decision"),
            "phase7_persisted": phase7_payload.get("persisted"),
            "phase7_trust_level": phase7_payload.get("trust_level"),
            "phase7_blocked_reason": phase7_payload.get("blocked_reason"),
        }

    @staticmethod
    def render_phase7_status(phase7: dict[str, object] | None) -> str:
        if not phase7:
            return "n/a"
        if phase7.get("persisted") is True:
            trust_level = phase7.get("trust_level") or "unknown"
            return f"persisted:{trust_level}"
        blocked_reason = phase7.get("blocked_reason") or "unknown"
        return f"blocked:{blocked_reason}"
