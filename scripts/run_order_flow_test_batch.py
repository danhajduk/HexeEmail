from __future__ import annotations

import asyncio
import json
import time
import tracemalloc
from pathlib import Path

from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.order_flow import GmailOrderPhase1Processor
from providers.gmail.order_phase2 import GmailOrderPhase2Scrubber
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor
from update_order_flow_tests import MAILS


def _ms(value: float) -> float:
    return round(value * 1000, 3)


def _format_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "min_ms": 0.0, "max_ms": 0.0, "avg_ms": 0.0}
    return {
        "count": float(len(values)),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
        "avg_ms": round(sum(values) / len(values), 3),
    }


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    runtime_dir = repo_root / "runtime"
    output_dir = runtime_dir / "order_flow_logs" / "test_1"
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter = GmailProviderAdapter(runtime_dir)
    phase1 = GmailOrderPhase1Processor()
    phase2 = GmailOrderPhase2Scrubber()
    phase3 = GmailOrderPhase3ProfileDetector()
    phase4 = GmailOrderPhase4Extractor()

    per_message_rows: list[dict[str, object]] = []
    phase1_times: list[float] = []
    phase2_times: list[float] = []
    phase3_times: list[float] = []
    phase4_times: list[float] = []
    total_times: list[float] = []
    cpu_times: list[float] = []
    peak_kib_values: list[float] = []

    for message_id, subject in MAILS:
        tracemalloc.start()
        total_wall_start = time.perf_counter()
        total_cpu_start = time.process_time()

        phase1_start = time.perf_counter()
        normalized = await phase1.fetch_and_normalize_message(
            adapter=adapter,
            account_id="primary",
            message_id=message_id,
        )
        phase1_ms = _ms(time.perf_counter() - phase1_start)

        phase2_start = time.perf_counter()
        scrubbed = phase2.scrub(normalized)
        phase2_ms = _ms(time.perf_counter() - phase2_start)

        phase3_start = time.perf_counter()
        profiled = phase3.detect(scrubbed)
        phase3_ms = _ms(time.perf_counter() - phase3_start)

        phase4_start = time.perf_counter()
        extracted = phase4.extract(profiled)
        phase4_ms = _ms(time.perf_counter() - phase4_start)

        total_ms = _ms(time.perf_counter() - total_wall_start)
        cpu_ms = _ms(time.process_time() - total_cpu_start)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_kib = round(peak_bytes / 1024, 3)

        phase1_times.append(phase1_ms)
        phase2_times.append(phase2_ms)
        phase3_times.append(phase3_ms)
        phase4_times.append(phase4_ms)
        total_times.append(total_ms)
        cpu_times.append(cpu_ms)
        peak_kib_values.append(peak_kib)

        log_text = (
            f"{message_id} {subject}\n\n"
            f"Full HTML:\n{normalized.raw_html or '[no html body]'}\n\n"
            f"Phase 1 output:\n{normalized.model_dump_json(indent=2)}\n\n"
            f"Phase 2 output:\n{scrubbed.model_dump_json(indent=2)}\n\n"
            f"Phase 3 output:\n{profiled.model_dump_json(indent=2)}\n\n"
            f"Phase 4 output:\n{extracted.model_dump_json(indent=2)}\n"
        )
        (output_dir / f"{message_id}.log").write_text(log_text, encoding="utf-8")

        per_message_rows.append(
            {
                "message_id": message_id,
                "subject": subject,
                "phase1_ms": phase1_ms,
                "phase2_ms": phase2_ms,
                "phase3_ms": phase3_ms,
                "phase4_ms": phase4_ms,
                "total_ms": total_ms,
                "cpu_ms": cpu_ms,
                "peak_python_alloc_kib": peak_kib,
                "phase1_status": normalized.fetch_status,
                "phase2_status": scrubbed.scrub_status,
                "phase3_status": profiled.profile_status,
                "phase4_status": extracted.extraction_status,
                "phase4_profile_id": extracted.profile_id,
                "phase4_template_id": extracted.template_id,
            }
        )

    summary = {
        "corpus_size": len(per_message_rows),
        "phase1": _format_stats(phase1_times),
        "phase2": _format_stats(phase2_times),
        "phase3": _format_stats(phase3_times),
        "phase4": _format_stats(phase4_times),
        "total": _format_stats(total_times),
        "cpu": _format_stats(cpu_times),
        "peak_python_alloc_kib": _format_stats(peak_kib_values),
    }
    benchmark_payload = {
        "output_dir": str(output_dir),
        "messages": per_message_rows,
        "summary": summary,
    }
    (output_dir / "benchmark_report.json").write_text(
        json.dumps(benchmark_payload, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# ORDER Flow Benchmark Report",
        "",
        f"Output directory: `{output_dir}`",
        f"Corpus size: `{len(per_message_rows)}`",
        "",
        "## Summary",
        "",
        f"- Phase 1 avg: `{summary['phase1']['avg_ms']} ms`",
        f"- Phase 2 avg: `{summary['phase2']['avg_ms']} ms`",
        f"- Phase 3 avg: `{summary['phase3']['avg_ms']} ms`",
        f"- Phase 4 avg: `{summary['phase4']['avg_ms']} ms`",
        f"- Total avg: `{summary['total']['avg_ms']} ms`",
        f"- Total max: `{summary['total']['max_ms']} ms`",
        f"- CPU avg: `{summary['cpu']['avg_ms']} ms`",
        f"- Peak Python alloc avg: `{summary['peak_python_alloc_kib']['avg_ms']} KiB`",
        "",
        "## Per Message",
        "",
        "| Message ID | Subject | P1 ms | P2 ms | P3 ms | P4 ms | Total ms | CPU ms | Peak KiB | P4 Status | Template |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in per_message_rows:
        lines.append(
            f"| `{row['message_id']}` | {row['subject']} | `{row['phase1_ms']}` | `{row['phase2_ms']}` | "
            f"`{row['phase3_ms']}` | `{row['phase4_ms']}` | `{row['total_ms']}` | `{row['cpu_ms']}` | "
            f"`{row['peak_python_alloc_kib']}` | `{row['phase4_status']}` | `{row['phase4_template_id'] or 'n/a'}` |"
        )
    (output_dir / "benchmark_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
