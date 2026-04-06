from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AppConfig
from email_node.patterns.pattern_generation_client import PatternGenerationClient
from email_node.patterns.pattern_generation_pipeline import PatternGenerationPipeline
from email_node.patterns.pattern_generation_request import PatternGenerationRequest
from email_node.patterns.pattern_generation_service import PatternGenerationService, PatternGenerationServiceError
from email_node.patterns.pattern_generation_writer import PatternGenerationWriter
from email_node.patterns.probation_store import ProbationStore
from email_node.pipeline.order_flow import OrderFlowPipeline
from email_node.shared_pipeline_core import SharedEmailPhase1Interface, SharedPhase1NormalizeRequest
from node_backend.runtime import RuntimeManager
from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.order_flow import GmailOrderPhase1Processor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ad hoc ORDER flow reports for specific Gmail message ids.")
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        metavar="LABEL=MESSAGE_ID",
        help="Add a report case, for example amazon=19d56c0462707ad1",
    )
    parser.add_argument("--account-id", default="primary")
    parser.add_argument("--suffix", default=f"adhoc-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    parser.add_argument("--enable-ai-generation", action="store_true")
    return parser.parse_args()


def to_data(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: to_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_data(item) for item in value]
    return value


def parse_cases(raw_cases: list[str]) -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    for item in raw_cases:
        if "=" not in item:
            raise SystemExit(f"Invalid --case value: {item!r}. Expected LABEL=MESSAGE_ID.")
        label, message_id = item.split("=", 1)
        label = label.strip()
        message_id = message_id.strip()
        if not label or not message_id:
            raise SystemExit(f"Invalid --case value: {item!r}. Expected LABEL=MESSAGE_ID.")
        cases.append((label, message_id))
    if not cases:
        raise SystemExit("At least one --case LABEL=MESSAGE_ID is required.")
    return cases


def render_phase7_status(phase7: dict[str, object] | None) -> str:
    if not phase7:
        return "n/a"
    if phase7.get("persisted") is True:
        trust_level = phase7.get("trust_level") or "unknown"
        return f"persisted:{trust_level}"
    blocked_reason = phase7.get("blocked_reason") or "unknown"
    return f"blocked:{blocked_reason}"


async def build_generator(config: AppConfig, probation_store: ProbationStore):
    target_api_base_url = RuntimeManager.normalize_target_api_base_url(None)
    client = PatternGenerationClient(target_api_base_url=target_api_base_url)
    service = PatternGenerationService(
        PatternGenerationPipeline(client),
        PatternGenerationWriter(base_dir=probation_store.templates_dir),
    )

    async def generate(request: PatternGenerationRequest) -> dict[str, object]:
        try:
            return await service.generate(request)
        except PatternGenerationServiceError as exc:
            raise ValueError(str(exc)) from exc

    return generate


async def main() -> None:
    args = parse_args()
    cases = parse_cases(args.case)
    config = AppConfig()
    runtime_dir = config.runtime_dir
    out_dir = runtime_dir / "order_flow_logs" / "ad_hoc_reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    adapter = GmailProviderAdapter(runtime_dir=runtime_dir)
    phase1 = SharedEmailPhase1Interface(GmailOrderPhase1Processor())
    probation_store = ProbationStore()
    generate_probation_template = await build_generator(config, probation_store) if args.enable_ai_generation else None
    pipeline = OrderFlowPipeline(
        runtime_dir=runtime_dir,
        probation_store=probation_store,
        generate_probation_template=generate_probation_template,
        ai_calls_enabled=lambda: True,
        order_checks_enabled=lambda: True,
    )

    ran_at = datetime.now(timezone.utc).isoformat()
    index: list[dict[str, object]] = []

    for label, message_id in cases:
        normalized = await phase1.normalize(
            SharedPhase1NormalizeRequest(
                fetch_full_message_payload=adapter.fetch_full_message_payload,
                account_id=args.account_id,
                message_id=message_id,
            )
        )
        result = await pipeline.process_normalized_email(normalized)
        payload = {
            "ran_at": ran_at,
            "label": label,
            "account_id": args.account_id,
            "message_id": message_id,
            "phase1": to_data(normalized),
            "phase2": to_data(result.get("phase2")),
            "phase3": to_data(result.get("phase3")),
            "phase4": to_data(result.get("phase4")),
            "phase6": to_data(result.get("phase6")),
            "phase7": to_data(result.get("phase7")),
            "phase7_result": to_data(result.get("phase7_result")),
            "action_gate": to_data(result.get("action_gate")),
            "action_router": to_data(result.get("action_router")),
            "order_record_write": to_data(result.get("order_record_write")),
            "user_notification": to_data(result.get("user_notification")),
            "tracking_monitor": to_data(result.get("tracking_monitor")),
        }

        base_name = f"{message_id}.order_flow_report.{args.suffix}"
        json_path = out_dir / f"{base_name}.json"
        md_path = out_dir / f"{base_name}.md"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        phase1_payload = payload["phase1"] or {}
        phase2_payload = payload["phase2"] or {}
        phase3_payload = payload["phase3"] or {}
        phase4_payload = payload["phase4"] or {}
        phase6_payload = payload["phase6"] or {}
        phase7_payload = payload["phase7"] or {}
        lines = [
            f"# ORDER Flow Report: {message_id}",
            "",
            f"- Label: `{label}`",
            f"- Account: `{args.account_id}`",
            f"- Ran at: `{ran_at}`",
            f"- Subject: `{phase1_payload.get('subject')}`",
            f"- Sender: `{phase1_payload.get('sender_email') or phase1_payload.get('sender')}`",
            "",
            "## Status",
            f"- Phase 1: `{phase1_payload.get('fetch_status')}`",
            f"- Phase 2: `{phase2_payload.get('scrub_status')}`",
            f"- Phase 3: `{phase3_payload.get('profile_status')}` / profile `{phase3_payload.get('profile_id')}` / confidence `{phase3_payload.get('profile_confidence')}` `{phase3_payload.get('profile_confidence_level')}`",
            f"- Phase 4: `{phase4_payload.get('extraction_status')}` / template `{phase4_payload.get('template_id')}` / extraction confidence `{phase4_payload.get('extraction_confidence')}` `{phase4_payload.get('extraction_confidence_level')}`",
            f"- Phase 6: `{phase6_payload.get('decision')}`",
            f"- Phase 7: `{render_phase7_status(phase7_payload)}`",
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
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        index.append(
            {
                "message_id": message_id,
                "label": label,
                "ran_at": ran_at,
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "phase3_profile": phase3_payload.get("profile_id"),
                "phase3_confidence": phase3_payload.get("profile_confidence"),
                "phase4_status": phase4_payload.get("extraction_status"),
                "phase4_template_id": phase4_payload.get("template_id"),
                "phase6_decision": phase6_payload.get("decision"),
                "phase7_persisted": phase7_payload.get("persisted"),
                "phase7_trust_level": phase7_payload.get("trust_level"),
                "phase7_blocked_reason": phase7_payload.get("blocked_reason"),
            }
        )

    index_path = out_dir / f"order_flow_report.{args.suffix}.index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(json.dumps({"ran_at": ran_at, "reports": index, "index": str(index_path)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
