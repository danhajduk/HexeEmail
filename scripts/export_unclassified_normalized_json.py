from __future__ import annotations

import json
from math import ceil
from pathlib import Path

from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.training import normalize_email_for_classifier


CHUNK_SIZE = 1000


def _load_unclassified_rows(adapter: GmailProviderAdapter, account_id: str) -> list[dict[str, object]]:
    with adapter.message_store._connect() as connection:
        rows = connection.execute(
            """
            SELECT
                account_id,
                message_id,
                thread_id,
                subject,
                sender,
                recipients,
                snippet,
                label_ids,
                received_at,
                raw_payload,
                local_label,
                local_label_confidence,
                manual_classification,
                action_decision_payload,
                action_decision_prompt_version,
                action_decision_updated_at,
                action_decision_raw_response,
                action_decision_raw_response_updated_at
            FROM gmail_messages
            WHERE account_id = ?
              AND (
                lower(COALESCE(local_label, '')) = 'unknown'
                OR trim(COALESCE(local_label, '')) = ''
              )
            ORDER BY datetime(received_at) DESC, message_id DESC
            """,
            (account_id,),
        ).fetchall()
    messages = [adapter.message_store._row_to_message(row) for row in rows]
    return [
        {
            "message_id": message.message_id,
            "received_at": message.received_at.isoformat(),
            "normalized_text": normalize_email_for_classifier(message, my_addresses=[]),
        }
        for message in messages
    ]


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    runtime_dir = repo_root / "runtime"
    output_dir = runtime_dir / "exports" / "unclassified_normalized_json"
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter = GmailProviderAdapter(runtime_dir)
    rows = _load_unclassified_rows(adapter, "primary")

    chunk_count = ceil(len(rows) / CHUNK_SIZE) if rows else 0
    manifest = {
        "output_dir": str(output_dir),
        "account_id": "primary",
        "chunk_size": CHUNK_SIZE,
        "total_records": len(rows),
        "chunk_count": chunk_count,
        "definition": "Includes messages where local_label is unknown, null, or blank. JSON shape mirrors normalized_emails_sample_1.txt fields.",
        "files": [],
    }

    for index in range(chunk_count):
        start = index * CHUNK_SIZE
        end = start + CHUNK_SIZE
        chunk_rows = rows[start:end]
        path = output_dir / f"unclassified_normalized_{index + 1:03d}.json"
        path.write_text(json.dumps(chunk_rows, indent=2) + "\n", encoding="utf-8")
        manifest["files"].append(
            {
                "file": path.name,
                "record_count": len(chunk_rows),
                "start_index": start,
                "end_index_exclusive": start + len(chunk_rows),
            }
        )

    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, **manifest}, indent=2))


if __name__ == "__main__":
    main()
