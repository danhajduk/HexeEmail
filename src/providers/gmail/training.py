from __future__ import annotations

import html
import json
import re
from email.utils import getaddresses, parseaddr

from providers.gmail.models import (
    GmailFlattenedMessage,
    GmailStoredMessage,
    GmailTrainingFlags,
    GmailTrainingRecipientFlags,
)


NORMALIZATION_VERSION = "v2"
MAX_BODY_PREVIEW_LENGTH = 1000
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
