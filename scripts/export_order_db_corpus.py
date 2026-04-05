from __future__ import annotations

import asyncio
import csv
import json
import sqlite3
import time
import tracemalloc
from pathlib import Path

from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.order_flow import GmailOrderPhase1Processor
from providers.gmail.order_phase2 import GmailOrderPhase2Scrubber
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


def _ms(value: float) -> float:
    return round(value * 1000, 3)


def _format_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0.0, "min_ms": 0.0, "max_ms": 0.0, "avg_ms": 0.0}
    return {
        "count": float(len(values)),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
        "avg_ms": round(sum(values) / len(values), 3),
    }


def _is_amazon(sender: str) -> bool:
    normalized = sender.strip().lower()
    return "amazon.com" in normalized or "<auto-confirm@amazon.com>" in normalized or "<order-update@amazon.com>" in normalized


def _load_order_messages(db_path: Path) -> list[dict[str, str]]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            select
                account_id,
                message_id,
                sender,
                subject
            from gmail_messages
            where lower(local_label) = 'order'
            order by datetime(received_at) desc, message_id desc
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "account_id": str(row["account_id"] or "").strip(),
            "message_id": str(row["message_id"] or "").strip(),
            "sender": str(row["sender"] or "").strip(),
            "subject": str(row["subject"] or "").strip(),
        }
        for row in rows
    ]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mail_id", "sender", "subject"])
        for row in rows:
            writer.writerow([row["message_id"], row["sender"], row["subject"]])


async def _run_group(
    *,
    name: str,
    rows: list[dict[str, str]],
    adapter: GmailProviderAdapter,
    output_dir: Path,
) -> None:
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

    final_outputs: list[dict[str, object]] = []

    for row in rows:
        message_id = row["message_id"]
        tracemalloc.start()
        total_wall_start = time.perf_counter()
        total_cpu_start = time.process_time()

        phase1_start = time.perf_counter()
        normalized = await phase1.fetch_and_normalize_message(
            adapter=adapter,
            account_id=row["account_id"],
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

        extracted_payload = extracted.model_dump(mode="json")
        final_outputs.append(
            {
                "account_id": row["account_id"],
                "message_id": message_id,
                "sender": row["sender"],
                "subject": row["subject"],
                "phase4_output": extracted_payload,
            }
        )
        per_message_rows.append(
            {
                "account_id": row["account_id"],
                "message_id": message_id,
                "sender": row["sender"],
                "subject": row["subject"],
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
                "profile_id": extracted.profile_id,
                "template_id": extracted.template_id,
            }
        )

    summary = {
        "group": name,
        "corpus_size": len(rows),
        "phase1": _format_stats(phase1_times),
        "phase2": _format_stats(phase2_times),
        "phase3": _format_stats(phase3_times),
        "phase4": _format_stats(phase4_times),
        "total": _format_stats(total_times),
        "cpu": _format_stats(cpu_times),
        "peak_python_alloc_kib": _format_stats(peak_kib_values),
    }
    benchmark_payload = {
        "group": name,
        "messages": per_message_rows,
        "summary": summary,
    }

    (output_dir / f"{name}_final_outputs.json").write_text(
        json.dumps(final_outputs, indent=2),
        encoding="utf-8",
    )
    (output_dir / f"{name}_benchmark.json").write_text(
        json.dumps(benchmark_payload, indent=2),
        encoding="utf-8",
    )
    lines = [
        f"# {name.replace('_', ' ').title()} ORDER Benchmark",
        "",
        f"Corpus size: `{len(rows)}`",
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
        "| Message ID | Sender | Subject | P1 ms | P2 ms | P3 ms | P4 ms | Total ms | CPU ms | Peak KiB | Status | Template |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in per_message_rows:
        lines.append(
            f"| `{row['message_id']}` | {row['sender']} | {row['subject']} | `{row['phase1_ms']}` | "
            f"`{row['phase2_ms']}` | `{row['phase3_ms']}` | `{row['phase4_ms']}` | `{row['total_ms']}` | "
            f"`{row['cpu_ms']}` | `{row['peak_python_alloc_kib']}` | `{row['phase4_status']}` | "
            f"`{row['template_id'] or 'n/a'}` |"
        )
    (output_dir / f"{name}_benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    runtime_dir = repo_root / "runtime"
    output_dir = runtime_dir / "order_flow_logs" / "db_order_exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = runtime_dir / "providers" / "gmail" / "messages.sqlite3"
    rows = _load_order_messages(db_path)
    amazon_rows = [row for row in rows if _is_amazon(row["sender"])]
    non_amazon_rows = [row for row in rows if not _is_amazon(row["sender"])]

    _write_csv(output_dir / "all_order_messages.csv", rows)
    _write_csv(output_dir / "amazon_order_messages.csv", amazon_rows)
    _write_csv(output_dir / "non_amazon_order_messages.csv", non_amazon_rows)

    adapter = GmailProviderAdapter(runtime_dir)
    await _run_group(name="amazon", rows=amazon_rows, adapter=adapter, output_dir=output_dir)
    await _run_group(name="non_amazon", rows=non_amazon_rows, adapter=adapter, output_dir=output_dir)

    manifest = {
        "output_dir": str(output_dir),
        "all_count": len(rows),
        "amazon_count": len(amazon_rows),
        "non_amazon_count": len(non_amazon_rows),
        "files": [
            "all_order_messages.csv",
            "amazon_order_messages.csv",
            "non_amazon_order_messages.csv",
            "amazon_final_outputs.json",
            "non_amazon_final_outputs.json",
            "amazon_benchmark.json",
            "amazon_benchmark.md",
            "non_amazon_benchmark.json",
            "non_amazon_benchmark.md",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
