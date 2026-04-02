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


def flatten_message(message: GmailStoredMessage, *, account_email: str | None = None) -> GmailFlattenedMessage:
    payload = _payload_json(message.raw_payload)
    headers = _header_map(payload)
    to_addresses = [address for _, address in getaddresses([headers.get("to", "")]) if address]
    cc_addresses = [address for _, address in getaddresses([headers.get("cc", "")]) if address]
    sender_name, sender_email = parseaddr(message.sender or "")
    del sender_name
    sender_email = sender_email.lower() or None
    sender_domain = sender_email.split("@", 1)[1] if sender_email and "@" in sender_email else None

    account_email_normalized = (account_email or "").lower()
    recipient_count = len({address.lower() for address in [*to_addresses, *cc_addresses] if address})
    to_me_only = bool(
        account_email_normalized
        and len(to_addresses) == 1
        and to_addresses[0].lower() == account_email_normalized
        and not cc_addresses
    )
    cc_me = bool(account_email_normalized and any(address.lower() == account_email_normalized for address in cc_addresses))
    subject = _clean_text(message.subject or headers.get("subject"))
    body_preview = _clean_preview(message.snippet)
    gmail_labels = list(message.label_ids)
    flags = GmailTrainingFlags(
        has_attachment=_has_attachment(payload),
        is_reply=bool(subject and subject.lower().startswith("re:")),
        is_forward=bool(subject and (subject.lower().startswith("fw:") or subject.lower().startswith("fwd:"))),
        has_unsubscribe=bool(headers.get("list-unsubscribe")) or "unsubscribe" in (body_preview or "").lower(),
    )

    return GmailFlattenedMessage(
        account_id=message.account_id,
        message_id=message.message_id,
        sender_email=sender_email,
        sender_domain=sender_domain,
        recipient=to_addresses[0] if to_addresses else (message.recipients[0] if message.recipients else None),
        recipient_flags=GmailTrainingRecipientFlags(
            to_me_only=to_me_only,
            cc_me=cc_me,
            recipient_count=recipient_count,
        ),
        subject=subject,
        flags=flags,
        body_preview=body_preview,
        gmail_labels=gmail_labels,
        local_label=message.local_label,
        local_label_confidence=message.local_label_confidence,
        manual_classification=message.manual_classification,
    )


def render_flat_training_text(flattened: GmailFlattenedMessage) -> str:
    labels = ",".join(flattened.gmail_labels) if flattened.gmail_labels else "-"
    return "\n".join(
        [
            f"from: {flattened.sender_email or '-'}",
            f"domain: {flattened.sender_domain or '-'}",
            f"to: {flattened.recipient or '-'}",
            (
                "recipient_flags: "
                f"to_me_only={str(flattened.recipient_flags.to_me_only).lower()} "
                f"cc_me={str(flattened.recipient_flags.cc_me).lower()} "
                f"recipient_count={flattened.recipient_flags.recipient_count}"
            ),
            f"subject: {flattened.subject or '-'}",
            (
                "flags: "
                f"has_attachment={str(flattened.flags.has_attachment).lower()} "
                f"is_reply={str(flattened.flags.is_reply).lower()} "
                f"is_forward={str(flattened.flags.is_forward).lower()} "
                f"has_unsubscribe={str(flattened.flags.has_unsubscribe).lower()}"
            ),
            f"body: {flattened.body_preview or '-'}",
            f"gmail_label: {labels}",
        ]
    )


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


def _clean_preview(value: str | None) -> str | None:
    return _clean_text(value)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    decoded = html.unescape(value)
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    normalized = re.sub(r"\s+", " ", without_tags).strip()
    return normalized or None


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
