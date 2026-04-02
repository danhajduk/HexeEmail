from __future__ import annotations

import html
import json
import re
from email.utils import getaddresses, parseaddr

from providers.gmail.models import (
    GmailFlattenedMessage,
    GmailStoredMessage,
    GmailTrainingDatasetRow,
    GmailTrainingDatasetSummary,
    GmailTrainingFlags,
    GmailTrainingLabel,
    GmailTrainingRecipientFlags,
)


NORMALIZATION_VERSION = "v2"
MAX_BODY_PREVIEW_LENGTH = 1000
EXCLUDED_MAILBOX_LABELS = {"SENT", "DRAFT", "TRASH", "SPAM"}
GMAIL_WEAK_LABEL_MAP = {
    "CATEGORY_PROMOTIONS": GmailTrainingLabel.MARKETING,
    "CATEGORY_UPDATES": GmailTrainingLabel.SYSTEM,
    "CATEGORY_FORUMS": GmailTrainingLabel.NEWSLETTER,
    "CATEGORY_SOCIAL": GmailTrainingLabel.NEWSLETTER,
    "CATEGORY_PERSONAL": GmailTrainingLabel.DIRECT_HUMAN,
}
SYSTEM_KEYWORDS = ("alert", "system", "notification", "notice", "status", "healthy", "downtime")
SECURITY_KEYWORDS = ("password", "verification", "verify", "security", "2fa", "login", "sign in", "suspicious")
SHIPMENT_KEYWORDS = ("tracking", "delivered", "delivery", "shipped", "shipment", "out for delivery")
ORDER_KEYWORDS = ("order", "purchase", "bought", "cart", "merchant")
INVOICE_KEYWORDS = ("invoice", "inv ", "bill", "receipt due")
FINANCIAL_KEYWORDS = ("payment", "balance", "statement", "debit", "credit", "account", "posted")
ACTION_REQUIRED_KEYWORDS = ("action required", "please review", "please respond", "need attention", "confirm", "approve")
DIRECT_HUMAN_KEYWORDS = ("can you", "please", "let me know", "following up", "reply")
REPLY_PREFIX_RE = re.compile(r"^(?:(?:re|fw|fwd)\s*:\s*)+", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+(?:[\d,./:-]*\d)?\b")
NON_PRINTING_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
PUNCT_RE = re.compile(r"[^a-z0-9\s]")
MULTISPACE_RE = re.compile(r"\s+")


def flatten_message(message: GmailStoredMessage, *, account_email: str | None = None) -> GmailFlattenedMessage:
    payload = _payload_json(message.raw_payload)
    headers = _header_map(payload)
    to_addresses = [address.lower() for _, address in getaddresses([headers.get("to", "")]) if address]
    cc_addresses = [address.lower() for _, address in getaddresses([headers.get("cc", "")]) if address]
    sender_email = _normalize_sender_email(message.sender)
    sender_domain = _extract_domain(sender_email)

    account_email_normalized = (account_email or "").strip().lower()
    visible_recipient_count = len({address for address in [*to_addresses, *cc_addresses] if address})
    subject = _normalize_subject(message.subject or headers.get("subject"))
    body_preview = _normalize_body(message.snippet)
    flags = GmailTrainingFlags(
        has_attachment=_has_attachment(payload),
        is_reply=bool((message.subject or "").strip().lower().startswith("re:")),
        is_forward=bool((message.subject or "").strip().lower().startswith(("fw:", "fwd:"))),
        has_unsubscribe=bool(headers.get("list-unsubscribe")) or "unsubscribe" in body_preview,
    )

    return GmailFlattenedMessage(
        account_id=message.account_id,
        message_id=message.message_id,
        sender_email=sender_email,
        sender_domain=sender_domain,
        recipient=None,
        recipient_flags=GmailTrainingRecipientFlags(
            to_me_only=bool(
                account_email_normalized
                and len(to_addresses) == 1
                and to_addresses[0] == account_email_normalized
                and not cc_addresses
            ),
            cc_me=bool(account_email_normalized and account_email_normalized in cc_addresses),
            recipient_count=_recipient_count_bucket(visible_recipient_count),
        ),
        subject=subject,
        flags=flags,
        body_preview=body_preview,
        gmail_labels=[],
        local_label=message.local_label,
        local_label_confidence=message.local_label_confidence,
        manual_classification=message.manual_classification,
    )


def render_flat_training_text(flattened: GmailFlattenedMessage) -> str:
    return "\n".join(
        [
            f"from: {flattened.sender_email or ''}",
            f"domain: {flattened.sender_domain or ''}",
            (
                "recipient_flags: "
                f"to_me_only={str(flattened.recipient_flags.to_me_only).lower()} "
                f"cc_me={str(flattened.recipient_flags.cc_me).lower()} "
                f"recipient_count={flattened.recipient_flags.recipient_count}"
            ),
            f"subject: {flattened.subject or ''}",
            (
                "flags: "
                f"has_attachment={str(flattened.flags.has_attachment).lower()} "
                f"is_reply={str(flattened.flags.is_reply).lower()} "
                f"is_forward={str(flattened.flags.is_forward).lower()} "
                f"has_unsubscribe={str(flattened.flags.has_unsubscribe).lower()}"
            ),
            f"body: {flattened.body_preview or ''}",
        ]
    )


def render_raw_training_text(message: GmailStoredMessage, *, label_names: dict[str, str] | None = None) -> str:
    payload = _payload_json(message.raw_payload)
    headers = _header_map(payload)
    recipients = [value for value in message.recipients if value]
    if not recipients:
        recipients = [address for _, address in getaddresses([headers.get("to", ""), headers.get("cc", "")]) if address]
    subject = _display_subject(message.subject or headers.get("subject"))
    body = _display_body(message.snippet)
    label_lookup = label_names or {}
    labels = ", ".join(label_lookup.get(label_id, label_id) for label_id in message.label_ids)
    return "\n".join(
        [
            f"from: {_display_sender(message.sender)}",
            f"to: {', '.join(recipients)}",
            f"subject: {subject}",
            f"labels: {labels}",
            f"body: {body}",
        ]
    )


def parse_label_ids(label_ids: str | list[str] | set[str] | None) -> set[str]:
    if label_ids is None:
        return set()
    if isinstance(label_ids, str):
        return {label.strip() for label in label_ids.splitlines() if label.strip()}
    if isinstance(label_ids, (list, set, tuple)):
        return {str(label).strip() for label in label_ids if str(label).strip()}
    return set()


def is_trainable_message(message: GmailStoredMessage | dict[str, object]) -> bool:
    if isinstance(message, GmailStoredMessage):
        labels = parse_label_ids(message.label_ids)
    else:
        labels = parse_label_ids(message.get("label_ids"))
    return not bool(labels & EXCLUDED_MAILBOX_LABELS)


def normalize_email_for_classifier(message: GmailStoredMessage, *, my_addresses: list[str] | None = None) -> str:
    account_email = next((address for address in (my_addresses or []) if address), None)
    flattened = flatten_message(message, account_email=account_email)
    return render_flat_training_text(flattened)


def propose_bootstrap_label(
    message: GmailStoredMessage,
    *,
    my_addresses: list[str] | None = None,
    threshold: float,
) -> tuple[GmailTrainingLabel | None, float, str | None]:
    flattened = flatten_message(message, account_email=next((address for address in (my_addresses or []) if address), None))
    labels = parse_label_ids(message.label_ids)
    text = f"{flattened.subject or ''} {flattened.body_preview or ''}".strip()
    scores: dict[GmailTrainingLabel, float] = {
        GmailTrainingLabel.MARKETING: 0.0,
        GmailTrainingLabel.SYSTEM: 0.0,
        GmailTrainingLabel.NEWSLETTER: 0.0,
        GmailTrainingLabel.DIRECT_HUMAN: 0.0,
        GmailTrainingLabel.SECURITY: 0.0,
        GmailTrainingLabel.SHIPMENT: 0.0,
        GmailTrainingLabel.ORDER: 0.0,
        GmailTrainingLabel.INVOICE: 0.0,
        GmailTrainingLabel.FINANCIAL: 0.0,
        GmailTrainingLabel.ACTION_REQUIRED: 0.0,
    }
    gmail_support: dict[GmailTrainingLabel, float] = {label: 0.0 for label in scores}

    if "CATEGORY_PROMOTIONS" in labels:
        scores[GmailTrainingLabel.MARKETING] += 3
        gmail_support[GmailTrainingLabel.MARKETING] += 3
    if flattened.flags.has_unsubscribe:
        scores[GmailTrainingLabel.MARKETING] += 2
        scores[GmailTrainingLabel.NEWSLETTER] += 1
    if flattened.recipient_flags.recipient_count in {"rc_4_10", "rc_10plus"}:
        scores[GmailTrainingLabel.MARKETING] += 1
    if not flattened.recipient_flags.to_me_only:
        scores[GmailTrainingLabel.MARKETING] += 1

    if "CATEGORY_UPDATES" in labels:
        scores[GmailTrainingLabel.SYSTEM] += 2
        gmail_support[GmailTrainingLabel.SYSTEM] += 2
    if _contains_any(text, SYSTEM_KEYWORDS):
        scores[GmailTrainingLabel.SYSTEM] += 2

    if "CATEGORY_FORUMS" in labels:
        scores[GmailTrainingLabel.NEWSLETTER] += 2
        gmail_support[GmailTrainingLabel.NEWSLETTER] += 2
    if "CATEGORY_SOCIAL" in labels:
        scores[GmailTrainingLabel.NEWSLETTER] += 1
        gmail_support[GmailTrainingLabel.NEWSLETTER] += 1

    if "CATEGORY_PERSONAL" in labels:
        scores[GmailTrainingLabel.DIRECT_HUMAN] += 1
        gmail_support[GmailTrainingLabel.DIRECT_HUMAN] += 1
    if flattened.recipient_flags.to_me_only:
        scores[GmailTrainingLabel.DIRECT_HUMAN] += 2
    if _contains_any(text, DIRECT_HUMAN_KEYWORDS):
        scores[GmailTrainingLabel.DIRECT_HUMAN] += 1
    if flattened.sender_email.startswith(("no-reply@", "noreply@", "donotreply@")):
        scores[GmailTrainingLabel.DIRECT_HUMAN] -= 2

    if _contains_any(text, SECURITY_KEYWORDS):
        scores[GmailTrainingLabel.SECURITY] += 3
    if _contains_any(text, SHIPMENT_KEYWORDS):
        scores[GmailTrainingLabel.SHIPMENT] += 3
    if _contains_any(text, ORDER_KEYWORDS):
        scores[GmailTrainingLabel.ORDER] += 2
    if _contains_any(text, INVOICE_KEYWORDS):
        scores[GmailTrainingLabel.INVOICE] += 3
    if _contains_any(text, FINANCIAL_KEYWORDS):
        scores[GmailTrainingLabel.FINANCIAL] += 2
    if _contains_any(text, ACTION_REQUIRED_KEYWORDS):
        scores[GmailTrainingLabel.ACTION_REQUIRED] += 3

    _apply_precedence_overrides(scores, text)
    label, score = max(scores.items(), key=lambda item: item[1])
    if score < threshold:
        return None, score, None
    source = "gmail_bootstrap" if gmail_support.get(label, 0.0) > 0 else "rule_bootstrap"
    return label, score, source


def resolve_training_label(
    message: GmailStoredMessage,
    bootstrap_result: tuple[GmailTrainingLabel | None, float, str | None],
) -> tuple[GmailTrainingLabel | None, str | None, float | None]:
    local_label = _coerce_training_label(message.local_label)
    if message.manual_classification and local_label is not None and local_label != GmailTrainingLabel.UNKNOWN:
        return local_label, "manual", 1.0
    if not message.manual_classification and local_label is not None and local_label != GmailTrainingLabel.UNKNOWN:
        confidence = float(message.local_label_confidence or 0.0)
        if confidence >= 0.85:
            return local_label, "local_auto", 0.75
        if confidence >= 0.70:
            return local_label, "local_auto", 0.50

    bootstrap_label, _, bootstrap_source = bootstrap_result
    if bootstrap_label is None or bootstrap_label == GmailTrainingLabel.UNKNOWN:
        return None, None, None
    return bootstrap_label, bootstrap_source, 0.30


def build_training_dataset(
    messages: list[GmailStoredMessage],
    *,
    my_addresses: list[str] | None = None,
    bootstrap_threshold: float,
    allow_bootstrap: bool = True,
) -> tuple[list[GmailTrainingDatasetRow], GmailTrainingDatasetSummary]:
    rows: list[GmailTrainingDatasetRow] = []
    summary = GmailTrainingDatasetSummary(
        total_rows_scanned=len(messages),
        excluded_mailbox_labels=sorted(EXCLUDED_MAILBOX_LABELS),
        gmail_mapping_config={key: value.value for key, value in GMAIL_WEAK_LABEL_MAP.items()},
        bootstrap_threshold=bootstrap_threshold,
    )
    for message in messages:
        if not is_trainable_message(message):
            summary.excluded_mailbox_count += 1
            continue
        normalized_text = normalize_email_for_classifier(message, my_addresses=my_addresses)
        bootstrap_result = (
            propose_bootstrap_label(message, my_addresses=my_addresses, threshold=bootstrap_threshold)
            if allow_bootstrap
            else (None, 0.0, None)
        )
        label, label_source, sample_weight = resolve_training_label(message, bootstrap_result)
        if label is None or label == GmailTrainingLabel.UNKNOWN or label_source is None or sample_weight is None:
            summary.excluded_no_label_count += 1
            continue
        row = GmailTrainingDatasetRow(
            account_id=message.account_id,
            message_id=message.message_id,
            normalized_text=normalized_text,
            label=label,
            label_source=label_source,
            sample_weight=sample_weight,
            normalization_version=NORMALIZATION_VERSION,
            received_at=message.received_at,
        )
        rows.append(row)
        summary.included_count += 1
        summary.included_by_label_source[label_source] = summary.included_by_label_source.get(label_source, 0) + 1
        summary.per_label_counts[label.value] = summary.per_label_counts.get(label.value, 0) + 1
        summary.weighted_counts[label.value] = round(summary.weighted_counts.get(label.value, 0.0) + sample_weight, 4)
    return rows, summary


def _normalize_sender_email(value: str | None) -> str:
    _, address = parseaddr(value or "")
    return address.strip().lower()


def _extract_domain(sender_email: str) -> str:
    if "@" not in sender_email:
        return ""
    return sender_email.split("@", 1)[1].strip().lower()


def _normalize_subject(value: str | None) -> str:
    if not value:
        return ""
    subject = _clean_display_text(value).strip().lower()
    subject = REPLY_PREFIX_RE.sub("", subject)
    subject = NUMBER_RE.sub("number", subject)
    subject = PUNCT_RE.sub(" ", subject)
    subject = MULTISPACE_RE.sub(" ", subject).strip()
    return subject


def _normalize_body(value: str | None) -> str:
    if not value:
        return ""
    body = _clean_display_text(value)
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(">"):
            continue
        lowered = line.lower()
        if lowered in {"--", "sent from my iphone", "sent from my android"}:
            continue
        lines.append(line)
    body = " ".join(lines)
    body = URL_RE.sub("url", body)
    body = NON_PRINTING_RE.sub("", body)
    body = NUMBER_RE.sub("number", body)
    body = PUNCT_RE.sub(" ", body.lower())
    body = MULTISPACE_RE.sub(" ", body).strip()
    return body[:MAX_BODY_PREVIEW_LENGTH].strip()


def _display_sender(value: str | None) -> str:
    return _clean_display_text(value).strip()


def _display_subject(value: str | None) -> str:
    return _clean_display_text(value).strip()


def _display_body(value: str | None) -> str:
    body = _clean_display_text(value)
    body = MULTISPACE_RE.sub(" ", body).strip()
    return body[:MAX_BODY_PREVIEW_LENGTH].strip()


def _clean_display_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = TAG_RE.sub(" ", text)
    text = NON_PRINTING_RE.sub("", text)
    return text


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _apply_precedence_overrides(scores: dict[GmailTrainingLabel, float], text: str) -> None:
    if _contains_any(text, SECURITY_KEYWORDS) and scores[GmailTrainingLabel.SECURITY] > 0:
        scores[GmailTrainingLabel.SECURITY] = max(scores[GmailTrainingLabel.SECURITY], scores[GmailTrainingLabel.SYSTEM] + 1)
    if _contains_any(text, SHIPMENT_KEYWORDS) and scores[GmailTrainingLabel.SHIPMENT] > 0:
        scores[GmailTrainingLabel.SHIPMENT] = max(scores[GmailTrainingLabel.SHIPMENT], scores[GmailTrainingLabel.ORDER] + 1)
    if _contains_any(text, INVOICE_KEYWORDS) and scores[GmailTrainingLabel.INVOICE] > 0:
        scores[GmailTrainingLabel.INVOICE] = max(scores[GmailTrainingLabel.INVOICE], scores[GmailTrainingLabel.FINANCIAL] + 1)
    if _contains_any(text, ACTION_REQUIRED_KEYWORDS) and scores[GmailTrainingLabel.ACTION_REQUIRED] > 0:
        scores[GmailTrainingLabel.ACTION_REQUIRED] = max(
            scores[GmailTrainingLabel.ACTION_REQUIRED],
            scores[GmailTrainingLabel.DIRECT_HUMAN] + 1,
        )


def _coerce_training_label(value: str | GmailTrainingLabel | None) -> GmailTrainingLabel | None:
    if value is None:
        return None
    if isinstance(value, GmailTrainingLabel):
        return value
    try:
        return GmailTrainingLabel(value)
    except ValueError:
        return None


def _recipient_count_bucket(count: int) -> str:
    if count <= 1:
        return "rc_1"
    if count <= 3:
        return "rc_2_3"
    if count <= 10:
        return "rc_4_10"
    return "rc_10plus"


def _payload_json(raw_payload: str | None) -> dict[str, object]:
    if not raw_payload:
        return {}
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _header_map(payload: dict[str, object]) -> dict[str, str]:
    headers = payload.get("payload", {}).get("headers") if isinstance(payload.get("payload"), dict) else []
    header_map: dict[str, str] = {}
    if isinstance(headers, list):
        for header in headers:
            if isinstance(header, dict):
                name = header.get("name")
                value = header.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    header_map[name.lower()] = value
    return header_map


def _has_attachment(payload: dict[str, object]) -> bool:
    root_payload = payload.get("payload")
    if not isinstance(root_payload, dict):
        return False
    parts = root_payload.get("parts")
    if not isinstance(parts, list):
        return False
    for part in parts:
        if isinstance(part, dict) and part.get("filename"):
            return True
    return False
