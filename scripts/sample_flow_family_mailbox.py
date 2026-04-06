from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from email_node.flow_families.action_required.runtime import ActionRequiredFlowRuntime
from email_node.flow_families.financial.runtime import FinancialFlowRuntime
from email_node.flow_families.invoice.runtime import InvoiceFlowRuntime
from email_node.flow_families.security.runtime import SecurityFlowRuntime
from email_node.flow_families.shipment.runtime import ShipmentFlowRuntime
from email_node.shared_pipeline_core.phase1 import SharedEmailPhase1Interface, SharedPhase1NormalizeRequest
from providers.gmail.models import GmailPhase2ScrubbedEmail, GmailPhase3DetectedEmail


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "runtime" / "providers" / "gmail" / "messages.sqlite3"
STOPWORDS = {
    "about",
    "after",
    "again",
    "all",
    "also",
    "and",
    "are",
    "been",
    "before",
    "below",
    "both",
    "but",
    "can",
    "did",
    "does",
    "each",
    "for",
    "from",
    "get",
    "got",
    "had",
    "has",
    "have",
    "here",
    "how",
    "into",
    "its",
    "just",
    "more",
    "new",
    "not",
    "now",
    "off",
    "our",
    "out",
    "over",
    "please",
    "should",
    "soon",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "too",
    "your",
    "you",
    "with",
    "will",
    "when",
    "what",
    "why",
}
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9'_-]{1,}")


@dataclass(slots=True)
class MessageRow:
    message_id: str
    subject: str
    sender: str
    received_at: str | None
    local_label_confidence: float | None
    raw_payload: dict[str, Any]


def _header_map_from_gmail_payload(payload: dict[str, Any]) -> dict[str, str]:
    root = payload.get("payload")
    headers = root.get("headers") if isinstance(root, dict) else []
    result: dict[str, str] = {}
    if isinstance(headers, list):
        for item in headers:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if isinstance(name, str) and isinstance(value, str):
                result[name.lower()] = value
    return result


def _coerce_full_message_payload(message_id: str, payload: dict[str, Any], *, received_at: str | None) -> dict[str, Any]:
    if isinstance(payload.get("text_body"), dict) or isinstance(payload.get("html_body"), dict):
        return payload
    headers = _header_map_from_gmail_payload(payload)
    snippet = str(payload.get("snippet") or "").strip()
    return {
        "message_id": str(payload.get("id") or message_id),
        "thread_id": payload.get("threadId") if isinstance(payload.get("threadId"), str) else None,
        "snippet": snippet or None,
        "subject": headers.get("subject"),
        "sender": headers.get("from"),
        "date": headers.get("date"),
        "received_at": received_at,
        "headers": headers,
        "text_body": {
            "content": snippet or None,
            "headers": headers,
            "content_transfer_encoding": None,
            "charset": None,
            "mime_boundary": None,
        }
        if snippet
        else None,
        "html_body": None,
        "fetch_status": "partial" if snippet else "failed",
        "fetch_error": None if snippet else "gmail stored payload did not include a snippet or body",
        "fetch_diagnostics": ["sampled_from_stored_gmail_payload"] + ([] if snippet else ["no_snippet_available"]),
        "mime_parse_status": "partial" if snippet else "failed",
        "mime_diagnostics": ["sampled_from_stored_gmail_payload"],
        "mime_boundaries": [],
        "part_inventory": [],
        "raw_payload": payload,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample a flow-family mailbox label and derive scrubbed taxonomy inputs.")
    parser.add_argument("family", choices=["financial", "invoice", "security", "shipment", "action_required"])
    parser.add_argument("--limit", type=int, default=30)
    return parser.parse_args()


def _runtime_for_family(family: str):
    if family == "financial":
        return FinancialFlowRuntime(runtime_dir=REPO_ROOT / "runtime")
    if family == "invoice":
        return InvoiceFlowRuntime(runtime_dir=REPO_ROOT / "runtime")
    if family == "security":
        return SecurityFlowRuntime(runtime_dir=REPO_ROOT / "runtime")
    if family == "shipment":
        return ShipmentFlowRuntime(runtime_dir=REPO_ROOT / "runtime")
    if family == "action_required":
        return ActionRequiredFlowRuntime(runtime_dir=REPO_ROOT / "runtime")
    raise ValueError(f"unsupported family: {family}")


def _db_rows_for_label(label: str, *, limit: int) -> tuple[int, list[MessageRow]]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        total_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM gmail_messages
            WHERE UPPER(COALESCE(local_label, '')) = ?
            """,
            (label.upper(),),
        ).fetchone()[0]
        rows = connection.execute(
            """
            SELECT message_id, subject, sender, received_at, local_label_confidence, raw_payload
            FROM gmail_messages
            WHERE UPPER(COALESCE(local_label, '')) = ?
              AND COALESCE(raw_payload, '') != ''
            ORDER BY received_at DESC, message_id DESC
            LIMIT ?
            """,
            (label.upper(), limit),
        ).fetchall()
    finally:
        connection.close()
    messages: list[MessageRow] = []
    for row in rows:
        raw_payload = row["raw_payload"]
        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        messages.append(
            MessageRow(
                message_id=str(row["message_id"]),
                subject=str(row["subject"] or ""),
                sender=str(row["sender"] or ""),
                received_at=(str(row["received_at"]) if row["received_at"] else None),
                local_label_confidence=(float(row["local_label_confidence"]) if row["local_label_confidence"] is not None else None),
                raw_payload=_coerce_full_message_payload(str(row["message_id"]), payload, received_at=(str(row["received_at"]) if row["received_at"] else None)),
            )
        )
    return int(total_count), messages


def _truncate(value: str | None, *, limit: int = 600) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _ngrams(text: str, *, sizes: tuple[int, ...] = (2, 3, 4)) -> set[str]:
    tokens = [token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOPWORDS and len(token) >= 3]
    result: set[str] = set()
    for size in sizes:
        if len(tokens) < size:
            continue
        for index in range(len(tokens) - size + 1):
            gram_tokens = tokens[index : index + size]
            if all(token in STOPWORDS for token in gram_tokens):
                continue
            result.add(" ".join(gram_tokens))
    return result


def _top_counter(counter: Counter[str], *, minimum: int = 2, limit: int = 25) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common()
        if count >= minimum
    ][:limit]


def _stringify_diagnostics(items: list[Any], *, limit: int = 8) -> list[str]:
    result: list[str] = []
    for item in items[:limit]:
        if isinstance(item, str):
            result.append(item)
            continue
        detail = getattr(item, "detail", None)
        code = getattr(item, "code", None)
        if code and detail:
            result.append(f"{code}:{detail}")
        elif detail:
            result.append(str(detail))
        elif code:
            result.append(str(code))
        else:
            result.append(str(item))
    return result


async def _analyze_family(family: str, *, limit: int) -> tuple[dict[str, Any], str]:
    total_count, messages = _db_rows_for_label(family, limit=limit)
    runtime = _runtime_for_family(family)
    phase1 = SharedEmailPhase1Interface()

    sender_domains = Counter[str]()
    profile_counts = Counter[str]()
    scrub_status_counts = Counter[str]()
    phase1_status_counts = Counter[str]()
    subject_ngrams = Counter[str]()
    scrubbed_ngrams = Counter[str]()
    leading_lines = Counter[str]()
    unresolved_leading_lines = Counter[str]()
    unresolved_domains = Counter[str]()
    samples: list[dict[str, Any]] = []

    for row in messages:
        async def fetch_full_message_payload(_account_id: str, _message_id: str, *, payload=row.raw_payload):
            return payload

        normalized = await phase1.normalize(
            SharedPhase1NormalizeRequest(
                fetch_full_message_payload=fetch_full_message_payload,
                account_id="sampled-local",
                message_id=row.message_id,
            )
        )
        phase2: GmailPhase2ScrubbedEmail = runtime.phase2_scrubber.scrub(normalized)
        phase3: GmailPhase3DetectedEmail = runtime.phase3_detector.detect(phase2)

        sender_domain = (phase3.sender_domain or normalized.sender_domain or "").strip().lower()
        if sender_domain:
            sender_domains[sender_domain] += 1
        phase1_status_counts[normalized.validation_status] += 1
        scrub_status_counts[phase2.scrub_status] += 1
        if phase3.profile_id:
            profile_counts[phase3.profile_id] += 1

        for gram in _ngrams(row.subject):
            subject_ngrams[gram] += 1
        for gram in _ngrams(phase2.scrubbed_text):
            scrubbed_ngrams[gram] += 1

        non_empty_lines = [line.strip() for line in phase2.normalized_lines if line.strip()]
        for line in non_empty_lines[:3]:
            leading_lines[line] += 1
        if not phase3.profile_id:
            for line in non_empty_lines[:3]:
                unresolved_leading_lines[line] += 1
            if sender_domain:
                unresolved_domains[sender_domain] += 1

        samples.append(
            {
                "message_id": row.message_id,
                "received_at": row.received_at,
                "subject": row.subject,
                "sender": row.sender,
                "sender_domain": sender_domain or None,
                "local_label_confidence": row.local_label_confidence,
                "phase1": {
                    "validation_status": normalized.validation_status,
                    "handoff_ready": normalized.handoff_ready,
                    "selected_body_type": normalized.selected_body_type,
                    "body_selection_reason": normalized.body_selection_reason,
                    "validation_diagnostics": list(normalized.validation_diagnostics[:8]),
                },
                "phase2": {
                    "scrub_status": phase2.scrub_status,
                    "transactional_quality": phase2.transactional_quality,
                    "scrubbed_text_preview": _truncate(phase2.scrubbed_text),
                    "leading_lines": non_empty_lines[:5],
                    "extracted_link_count": len(phase2.extracted_links),
                    "scrub_diagnostics": list(phase2.scrub_diagnostics[:8]),
                },
                "phase3": {
                    "profile_id": phase3.profile_id,
                    "profile_confidence": phase3.profile_confidence,
                    "profile_confidence_level": phase3.profile_confidence_level,
                    "profile_status": phase3.profile_status,
                    "top_candidates": [
                        {
                            "profile_id": candidate.profile_id,
                            "score": candidate.score,
                            "confidence_level": candidate.confidence_level,
                            "reasons": list(candidate.reasons[:6]),
                        }
                        for candidate in phase3.candidate_profiles[:3]
                    ],
                    "profile_diagnostics": list(phase3.profile_diagnostics[:10]),
                },
            }
        )

    generated_at = datetime.now().astimezone().isoformat()
    artifact = {
        "schema_version": "flow-family-mailbox-sample.v1",
        "flow_family": family,
        "generated_at": generated_at,
        "sample_limit": limit,
        "sample_size": len(samples),
        "total_labelled_messages": total_count,
        "aggregate": {
            "phase1_validation_status_counts": dict(phase1_status_counts),
            "phase2_scrub_status_counts": dict(scrub_status_counts),
            "phase3_profile_counts": dict(profile_counts),
            "top_sender_domains": _top_counter(sender_domains, minimum=1, limit=20),
            "top_subject_ngrams": _top_counter(subject_ngrams, minimum=2, limit=25),
            "top_scrubbed_ngrams": _top_counter(scrubbed_ngrams, minimum=2, limit=25),
            "top_leading_lines": _top_counter(leading_lines, minimum=2, limit=20),
            "unresolved_sender_domains": _top_counter(unresolved_domains, minimum=1, limit=15),
            "unresolved_leading_lines": _top_counter(unresolved_leading_lines, minimum=1, limit=20),
            "taxonomy_inputs": {
                "candidate_vendor_domains": _top_counter(sender_domains, minimum=1, limit=15),
                "candidate_subject_phrases": _top_counter(subject_ngrams, minimum=2, limit=15),
                "candidate_scrubbed_phrases": _top_counter(scrubbed_ngrams, minimum=2, limit=15),
                "unresolved_vendor_domains": _top_counter(unresolved_domains, minimum=1, limit=15),
                "unresolved_leading_lines": _top_counter(unresolved_leading_lines, minimum=1, limit=15),
            },
        },
        "messages": samples,
    }

    summary_lines = [
        f"# {family.upper()} Mailbox Sample",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Sample size: `{len(samples)}` of `{total_count}` labelled messages",
        "",
        "## Aggregate",
        "",
        f"- Phase 1 validation statuses: `{dict(phase1_status_counts)}`",
        f"- Phase 2 scrub statuses: `{dict(scrub_status_counts)}`",
        f"- Phase 3 profile counts: `{dict(profile_counts)}`",
        "",
        "## Taxonomy Inputs",
        "",
        "- Candidate vendor domains:",
    ]
    for item in _top_counter(sender_domains, minimum=1, limit=10):
        summary_lines.append(f"  - `{item['value']}`: `{item['count']}`")

    summary_lines.append("- Candidate subject phrases:")
    for item in _top_counter(subject_ngrams, minimum=2, limit=10):
        summary_lines.append(f"  - `{item['value']}`: `{item['count']}`")

    summary_lines.append("- Candidate scrubbed phrases:")
    for item in _top_counter(scrubbed_ngrams, minimum=2, limit=10):
        summary_lines.append(f"  - `{item['value']}`: `{item['count']}`")

    summary_lines.extend([
        "",
        "## Top Sender Domains",
        "",
    ])
    for item in _top_counter(sender_domains, minimum=1, limit=10):
        summary_lines.append(f"- `{item['value']}`: `{item['count']}`")

    summary_lines.extend(["", "## Top Subject Phrases", ""])
    for item in _top_counter(subject_ngrams, minimum=2, limit=12):
        summary_lines.append(f"- `{item['value']}`: `{item['count']}`")

    summary_lines.extend(["", "## Top Scrubbed Phrases", ""])
    for item in _top_counter(scrubbed_ngrams, minimum=2, limit=12):
        summary_lines.append(f"- `{item['value']}`: `{item['count']}`")

    summary_lines.extend(["", "## Unresolved Patterns", ""])
    if unresolved_domains:
        summary_lines.append("- Sender domains without a Phase 3 profile:")
        for item in _top_counter(unresolved_domains, minimum=1, limit=10):
            summary_lines.append(f"  - `{item['value']}`: `{item['count']}`")
    else:
        summary_lines.append("- All sampled messages resolved to a Phase 3 profile.")
    if unresolved_leading_lines:
        summary_lines.append("- Leading scrubbed lines from unresolved messages:")
        for item in _top_counter(unresolved_leading_lines, minimum=1, limit=10):
            summary_lines.append(f"  - `{item['value']}`: `{item['count']}`")

    summary_lines.extend(["", "## Sample Highlights", ""])
    for sample in samples[:8]:
        summary_lines.append(
            f"- `{sample['message_id']}` `{sample['phase3']['profile_id'] or 'no_profile'}` "
            f"from `{sample['sender_domain'] or 'unknown'}`: "
            f"`{_truncate(sample['phase2']['scrubbed_text_preview'], limit=140)}`"
        )

    return artifact, "\n".join(summary_lines) + "\n"


async def _main() -> int:
    args = _parse_args()
    artifact, summary = await _analyze_family(args.family, limit=args.limit)
    analysis_dir = REPO_ROOT / "runtime" / "flow_families" / args.family / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    json_path = analysis_dir / f"{args.family}_mailbox_sample.json"
    md_path = analysis_dir / f"{args.family}_mailbox_sample.md"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    md_path.write_text(summary, encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
