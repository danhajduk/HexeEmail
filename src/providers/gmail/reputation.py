from __future__ import annotations

from email.utils import parseaddr

from providers.gmail.models import (
    GmailSenderReputationInputs,
    GmailSenderReputationRecord,
    GmailSpamhausCheck,
    GmailStoredMessage,
    GmailTrainingLabel,
)

COMMON_MAILBOX_PROVIDER_DOMAINS = {
    "aol.com",
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "mac.com",
    "me.com",
    "msn.com",
    "outlook.com",
    "pm.me",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
    "ymail.com",
}
MULTI_LABEL_PUBLIC_SUFFIXES = {
    "ac.uk",
    "co.jp",
    "co.kr",
    "co.nz",
    "co.uk",
    "com.au",
    "com.br",
    "com.mx",
    "com.sg",
    "gov.uk",
    "net.au",
    "org.au",
    "org.uk",
}


POSITIVE_REPUTATION_LABELS = {
    GmailTrainingLabel.ACTION_REQUIRED.value,
    GmailTrainingLabel.DIRECT_HUMAN.value,
    GmailTrainingLabel.FINANCIAL.value,
    GmailTrainingLabel.ORDER.value,
    GmailTrainingLabel.INVOICE.value,
    GmailTrainingLabel.SHIPMENT.value,
    GmailTrainingLabel.SECURITY.value,
    GmailTrainingLabel.SYSTEM.value,
}
NEGATIVE_REPUTATION_LABELS = {
    GmailTrainingLabel.MARKETING.value,
    GmailTrainingLabel.NEWSLETTER.value,
}


def build_sender_reputation_records(
    messages: list[GmailStoredMessage],
    spamhaus_checks: list[GmailSpamhausCheck],
) -> list[GmailSenderReputationRecord]:
    message_by_id = {message.message_id: message for message in messages}
    records_by_key: dict[tuple[str, str, str], GmailSenderReputationRecord] = {}

    for message in messages:
        sender_email = _normalize_sender_email(message.sender)
        sender_domain = _extract_domain(sender_email)
        if not sender_email and not sender_domain:
            continue
        local_label = (message.local_label or "").strip().lower()
        entities = _entities_for_sender(sender_email=sender_email, sender_domain=sender_domain)
        for entity_type, sender_value in entities:
            record = records_by_key.get((message.account_id, entity_type, sender_value))
            if record is None:
                record_sender_domain = sender_domain
                if entity_type == "business_domain":
                    record_sender_domain = sender_value
                record = GmailSenderReputationRecord(
                    account_id=message.account_id,
                    entity_type=entity_type,
                    sender_value=sender_value,
                    sender_email=sender_email or None,
                    sender_domain=record_sender_domain or None,
                    group_domain=_group_domain_for_sender_domain(sender_domain) or None,
                )
                records_by_key[(message.account_id, entity_type, sender_value)] = record
            record.inputs.message_count += 1
            if local_label in POSITIVE_REPUTATION_LABELS:
                record.inputs.classification_positive_count += 1
            elif local_label in NEGATIVE_REPUTATION_LABELS:
                record.inputs.classification_negative_count += 1
            if record.last_seen_at is None or message.received_at > record.last_seen_at:
                record.last_seen_at = message.received_at

    for check in spamhaus_checks:
        message = message_by_id.get(check.message_id)
        sender_email = (check.sender_email or _normalize_sender_email(message.sender if message is not None else None)).strip().lower()
        sender_domain = (check.sender_domain or _extract_domain(sender_email)).strip().lower()
        if not sender_email and not sender_domain:
            continue
        for entity_type, sender_value in _entities_for_sender(sender_email=sender_email, sender_domain=sender_domain):
            record = records_by_key.get((check.account_id, entity_type, sender_value))
            if record is None:
                record_sender_domain = sender_domain
                if entity_type == "business_domain":
                    record_sender_domain = sender_value
                record = GmailSenderReputationRecord(
                    account_id=check.account_id,
                    entity_type=entity_type,
                    sender_value=sender_value,
                    sender_email=sender_email or None,
                    sender_domain=record_sender_domain or None,
                    group_domain=_group_domain_for_sender_domain(sender_domain) or None,
                    last_seen_at=message.received_at if message is not None else None,
                )
                records_by_key[(check.account_id, entity_type, sender_value)] = record
            if check.checked and check.status == "clean":
                record.inputs.spamhaus_clean_count += 1
            if check.listed or check.status == "listed":
                record.inputs.spamhaus_listed_count += 1

    records = list(records_by_key.values())
    for record in records:
        finalize_sender_reputation_record(record)
    records.sort(
        key=lambda record: (
            (record.last_seen_at.isoformat() if record.last_seen_at is not None else ""),
            record.sender_value,
        ),
        reverse=True,
    )
    return records


def finalize_sender_reputation_record(record: GmailSenderReputationRecord) -> GmailSenderReputationRecord:
    if not record.group_domain:
        record.group_domain = _group_domain_for_sender_domain(record.sender_domain) or None
    record.derived_rating = _derive_reputation_rating(record.inputs)
    manual_rating = float(record.manual_rating) if record.manual_rating is not None else 0.0
    record.rating = round(record.derived_rating + manual_rating, 2)
    record.reputation_state = _derive_reputation_state(record.inputs, record.rating)
    return record


def sender_matches_reputation_entity(
    *,
    entity_type: str,
    sender_email: str,
    sender_domain: str,
    sender_value: str,
) -> bool:
    if entity_type == "email":
        return sender_email == sender_value
    if entity_type == "domain":
        return sender_domain == sender_value
    if entity_type == "business_domain":
        return _business_domain_for_sender_domain(sender_domain) == sender_value
    return False


def _derive_reputation_rating(inputs: GmailSenderReputationInputs) -> float:
    rating = 0.0
    rating += float(inputs.classification_positive_count)
    rating -= float(inputs.classification_negative_count)
    rating += float(inputs.spamhaus_clean_count) * 0.25
    rating -= float(inputs.spamhaus_listed_count) * 4.0
    return round(rating, 2)


def _derive_reputation_state(
    inputs: GmailSenderReputationInputs,
    rating: float,
) -> str:
    if inputs.spamhaus_listed_count > 0:
        return "blocked"
    if rating >= 4.0 or (
        inputs.classification_positive_count >= 3
        and inputs.classification_negative_count == 0
    ):
        return "trusted"
    if rating < 0 or inputs.classification_negative_count > inputs.classification_positive_count:
        return "risky"
    return "neutral"


def _entities_for_sender(
    *,
    sender_email: str,
    sender_domain: str,
) -> list[tuple[str, str]]:
    entities: list[tuple[str, str]] = []
    if sender_email:
        entities.append(("email", sender_email))
    if sender_domain:
        entities.append(("domain", sender_domain))
        business_domain = _business_domain_for_sender_domain(sender_domain)
        if business_domain and business_domain != sender_domain:
            entities.append(("business_domain", business_domain))
    return entities


def _normalize_sender_email(value: str | None) -> str:
    _, address = parseaddr(value or "")
    return address.strip().lower()


def _extract_domain(sender_email: str) -> str:
    if "@" not in sender_email:
        return ""
    return sender_email.split("@", 1)[1].strip().lower()


def _group_domain_for_sender_domain(sender_domain: str | None) -> str:
    normalized = (sender_domain or "").strip().lower()
    if not normalized:
        return ""
    return _business_domain_for_sender_domain(normalized) or normalized


def _business_domain_for_sender_domain(sender_domain: str | None) -> str:
    normalized = (sender_domain or "").strip().lower()
    if not normalized:
        return ""
    registrable = _registrable_domain(normalized)
    if not registrable or registrable in COMMON_MAILBOX_PROVIDER_DOMAINS:
        return ""
    return registrable


def _registrable_domain(sender_domain: str) -> str:
    labels = [label for label in sender_domain.split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    last_two = ".".join(labels[-2:])
    last_three = ".".join(labels[-3:])
    if last_two in MULTI_LABEL_PUBLIC_SUFFIXES and len(labels) >= 3:
        return last_three
    return last_two
