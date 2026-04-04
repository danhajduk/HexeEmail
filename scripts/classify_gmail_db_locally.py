from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from config import AppConfig
from providers.gmail.adapter import GmailProviderAdapter
from providers.gmail.models import GmailStoredMessage, GmailTrainingLabel
from providers.gmail.training import normalize_email_for_classifier


def _load_non_manual_messages(adapter: GmailProviderAdapter, account_id: str) -> list[GmailStoredMessage]:
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
              AND manual_classification = 0
            ORDER BY received_at ASC
            """,
            (account_id,),
        ).fetchall()
    return [adapter.message_store._row_to_message(row) for row in rows]


def _label_counts(adapter: GmailProviderAdapter, account_id: str) -> dict[str, int]:
    with adapter.message_store._connect() as connection:
        rows = connection.execute(
            """
            SELECT COALESCE(local_label, '<null>') AS label_value, COUNT(*) AS count_value
            FROM gmail_messages
            WHERE account_id = ?
            GROUP BY COALESCE(local_label, '<null>')
            ORDER BY count_value DESC, label_value ASC
            """,
            (account_id,),
        ).fetchall()
    return {str(row["label_value"]): int(row["count_value"]) for row in rows}


def _manual_count(adapter: GmailProviderAdapter, account_id: str) -> int:
    with adapter.message_store._connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count_value
            FROM gmail_messages
            WHERE account_id = ?
              AND manual_classification = 1
            """,
            (account_id,),
        ).fetchone()
    return int(row["count_value"]) if row is not None else 0


def _persist_predictions(
    adapter: GmailProviderAdapter,
    account_id: str,
    updates: list[tuple[str, str, float]],
) -> None:
    if not updates:
        return
    with adapter.message_store._connect() as connection:
        connection.executemany(
            """
            UPDATE gmail_messages
            SET local_label = ?, local_label_confidence = ?, manual_classification = 0
            WHERE account_id = ? AND message_id = ?
            """,
            [(label, confidence, account_id, message_id) for message_id, label, confidence in updates],
        )
        connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify the full Gmail message store with the local repo model only.")
    parser.add_argument("--account-id", default="primary")
    parser.add_argument("--runtime-dir", default="runtime")
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    config = AppConfig()
    runtime_dir = Path(args.runtime_dir)
    threshold = float(args.threshold if args.threshold is not None else config.gmail_local_classification_threshold)
    adapter = GmailProviderAdapter(runtime_dir)
    status = adapter.training_model_store.status()
    if not bool(status.get("trained")):
        raise SystemExit("Local Gmail training model is not trained.")

    account_record = adapter.account_store.load_account(args.account_id)
    my_addresses = [account_record.email_address] if account_record is not None and account_record.email_address else []

    before_counts = _label_counts(adapter, args.account_id)
    manual_count = _manual_count(adapter, args.account_id)
    messages = _load_non_manual_messages(adapter, args.account_id)
    normalized_texts = [normalize_email_for_classifier(message, my_addresses=my_addresses) for message in messages]
    predictions = adapter.training_model_store.predict(normalized_texts, threshold=threshold)

    changed_messages: list[dict[str, object]] = []
    raw_predicted_counts: Counter[str] = Counter()
    predicted_counts: Counter[str] = Counter()
    changed_count = 0
    updates: list[tuple[str, str, float]] = []

    for message, prediction in zip(messages, predictions, strict=False):
        predicted_label = GmailTrainingLabel(str(prediction["predicted_label"]))
        predicted_confidence = float(prediction["predicted_confidence"])
        raw_predicted_label = str(prediction["raw_predicted_label"])
        raw_predicted_counts[raw_predicted_label] += 1
        predicted_counts[predicted_label.value] += 1

        previous_label = str(message.local_label) if message.local_label else None
        previous_confidence = float(message.local_label_confidence) if message.local_label_confidence is not None else None
        if previous_label != predicted_label.value or previous_confidence != predicted_confidence:
            changed_count += 1
            if len(changed_messages) < 200:
                changed_messages.append(
                    {
                        "message_id": message.message_id,
                        "subject": message.subject,
                        "previous_label": previous_label,
                        "new_label": predicted_label.value,
                        "previous_confidence": previous_confidence,
                        "new_confidence": predicted_confidence,
                        "raw_predicted_label": raw_predicted_label,
                    }
                )

        updates.append((message.message_id, predicted_label.value, predicted_confidence))

    _persist_predictions(adapter, args.account_id, updates)

    after_counts = _label_counts(adapter, args.account_id)
    generated_at = datetime.now().astimezone().isoformat()
    report = {
        "generated_at": generated_at,
        "account_id": args.account_id,
        "runtime_dir": str(runtime_dir),
        "threshold": threshold,
        "model_status": status,
        "manual_classification_count_preserved": manual_count,
        "auto_messages_processed": len(messages),
        "changed_auto_messages": changed_count,
        "predicted_counts_non_manual_only": dict(sorted(predicted_counts.items())),
        "raw_predicted_counts_non_manual_only": dict(sorted(raw_predicted_counts.items())),
        "before_label_counts_full_db": before_counts,
        "after_label_counts_full_db": after_counts,
        "changed_message_samples": changed_messages,
    }

    report_dir = runtime_dir / "providers" / "gmail" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "full_local_classification_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(
        {
            "ok": True,
            "report_path": str(report_path),
            "auto_messages_processed": len(messages),
            "changed_auto_messages": changed_count,
            "manual_classification_count_preserved": manual_count,
            "threshold": threshold,
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
