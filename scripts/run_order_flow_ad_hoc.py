from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

from config import AppConfig
from email_node.patterns.pattern_generation_client import PatternGenerationClient
from email_node.patterns.pattern_generation_pipeline import PatternGenerationPipeline
from email_node.patterns.pattern_generation_request import PatternGenerationRequest
from email_node.patterns.pattern_generation_service import PatternGenerationService, PatternGenerationServiceError
from email_node.patterns.pattern_generation_writer import PatternGenerationWriter
from email_node.patterns.probation_store import ProbationStore
from email_node.pipeline.order_flow import OrderFlowPipeline
from email_node.shared_pipeline_core import (
    SharedEmailPhase1Interface,
    SharedFlowReportBuilder,
    SharedPhase1NormalizeRequest,
)
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
    report_builder = SharedFlowReportBuilder()
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
        payload = report_builder.build_payload(
            ran_at=ran_at,
            label=label,
            account_id=args.account_id,
            message_id=message_id,
            normalized=normalized,
            flow_result=result,
        )

        base_name = f"{message_id}.order_flow_report.{args.suffix}"
        json_path = out_dir / f"{base_name}.json"
        md_path = out_dir / f"{base_name}.md"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path.write_text(report_builder.build_markdown(payload), encoding="utf-8")
        index.append(report_builder.build_index_entry(payload=payload, json_path=json_path, markdown_path=md_path))

    index_path = out_dir / f"order_flow_report.{args.suffix}.index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(json.dumps({"ran_at": ran_at, "reports": index, "index": str(index_path)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
