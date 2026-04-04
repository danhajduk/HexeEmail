from __future__ import annotations

import asyncio
import re
from pathlib import Path

from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.order_flow import GmailOrderPhase1Processor
from providers.gmail.order_phase2 import GmailOrderPhase2Scrubber
from providers.gmail.order_phase3 import GmailOrderPhase3ProfileDetector
from providers.gmail.order_phase4 import GmailOrderPhase4Extractor


MAILS = [
    ("19d56c0462707ad1", 'Ordered: "ESP32-S3-BOX-3B Development..."'),
    ("19d56bfe20f1cd41", 'Item cancelled successfully: "ESP32-S3-BOX-3B Development..."'),
    ("19d562c2ccde6e4a", 'Ordered: "The Ordinary Azelaic Acid..."'),
    ("19d55702ba2a0e53", 'Ordered: "Kawaye for Meta Quest..."'),
    ("19d521e1e27ea09d", "Your Upcoming Commuter Benefits Order"),
    ("19d2c286d303860f", "Recreation.gov Reservation Confirmation"),
    ("19d1d13c08183219", "Thanks for your curbside pickup order, Dan"),
    ("19d0e6192e79fe4a", 'Ordered: "Amazon Essentials Men\'s..."'),
    ("19ce96c056481da8", "Your Nectar - Hillsboro order is ready for pickup!"),
    ("19c92449347f6365", "Hi SLOBODAN please activate your RentalCover account. Reference: 48UB-4Y9N-INS"),
]


def _replace_or_append_block(entry: str, block_label: str, block_json: str) -> str:
    marker = f"\n{block_label}:\n"
    next_markers = ["\nPhase 1 output:\n", "\nPhase 2 output:\n", "\nPhase 3 output:\n"]
    if marker in entry:
        start = entry.index(marker)
        after_start = start + len(marker)
        end = len(entry)
        for next_marker in next_markers:
            if next_marker == marker:
                continue
            position = entry.find(next_marker, after_start)
            if position != -1:
                end = min(end, position)
        return entry[:start] + f"{marker}{block_json}\n" + entry[end:]
    return entry.rstrip() + f"\n\n{block_label}:\n{block_json}\n"


def update_doc_entry(
    existing: str,
    *,
    message_id: str,
    subject: str,
    phase1_json: str,
    phase2_json: str,
    phase3_json: str,
    phase4_json: str,
) -> str:
    entry_header = f"{message_id} | {subject}"
    if entry_header not in existing:
        suffix = (
            f"\n{entry_header}\n\n"
            f"Phase 1 output:\n{phase1_json}\n\n"
            f"Phase 2 output:\n{phase2_json}\n\n"
            f"Phase 3 output:\n{phase3_json}\n\n"
            f"Phase 4 output:\n{phase4_json}\n"
        )
        return existing.rstrip() + "\n\n" + suffix.lstrip()
    header_index = existing.index(entry_header)
    next_header_match = re.search(r"^\w[^\n]*\|", existing[header_index + len(entry_header):], re.MULTILINE)
    entry_end = header_index + len(entry_header) + next_header_match.start() if next_header_match else len(existing)
    entry = existing[header_index:entry_end]
    if "Phase 1 output:\n" not in entry:
        entry = f"{entry_header}\n\nPhase 1 output:\n{phase1_json}\n\n"
    if "Phase 2 output:\n" not in entry:
        entry = _replace_or_append_block(entry, "Phase 2 output", phase2_json)
    if "Phase 3 output:\n" not in entry:
        entry = _replace_or_append_block(entry, "Phase 3 output", phase3_json)
    entry = _replace_or_append_block(entry, "Phase 4 output", phase4_json)
    return existing[:header_index] + entry + existing[entry_end:]


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    runtime_dir = repo_root / "runtime"
    log_dir = runtime_dir / "order_flow_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    doc_path = repo_root / "docs" / "order_flow_tests.md"
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""

    adapter = GmailProviderAdapter(runtime_dir)
    phase1 = GmailOrderPhase1Processor()
    phase2 = GmailOrderPhase2Scrubber()
    phase3 = GmailOrderPhase3ProfileDetector()
    phase4 = GmailOrderPhase4Extractor()

    for message_id, subject in MAILS:
        normalized = await phase1.fetch_and_normalize_message(
            adapter=adapter,
            account_id="primary",
            message_id=message_id,
        )
        scrubbed = phase2.scrub(normalized)
        profiled = phase3.detect(scrubbed)
        extracted = phase4.extract(profiled)
        phase1_json = normalized.model_dump_json(indent=2)
        phase2_json = scrubbed.model_dump_json(indent=2)
        phase3_json = profiled.model_dump_json(indent=2)
        phase4_json = extracted.model_dump_json(indent=2)

        log_path = log_dir / f"{message_id}.log"
        existing_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        if "Phase 1 output:" not in existing_log:
            updated_log = (
                f"{message_id} {subject}\n\n\n"
                f"Phase 1 output:\n{phase1_json}\n\n"
                f"Phase 2 output:\n{phase2_json}\n\n"
                f"Phase 3 output:\n{phase3_json}\n\n"
                f"Phase 4 output:\n{phase4_json}\n"
            )
        else:
            updated_log = _replace_or_append_block(existing_log.rstrip(), "Phase 4 output", phase4_json) + "\n"
        log_path.write_text(updated_log, encoding="utf-8")
        doc_text = update_doc_entry(
            doc_text,
            message_id=message_id,
            subject=subject,
            phase1_json=phase1_json,
            phase2_json=phase2_json,
            phase3_json=phase3_json,
            phase4_json=phase4_json,
        )

    doc_path.write_text(doc_text.rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
