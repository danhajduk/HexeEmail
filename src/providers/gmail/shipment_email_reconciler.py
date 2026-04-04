from __future__ import annotations

import re
from email.utils import parseaddr

from logging_utils import get_logger
from providers.gmail.message_store import GmailMessageStore
from providers.gmail.models import GmailShipmentRecord, GmailShipmentScrubResult, GmailStoredMessage


LOGGER = get_logger(__name__)


SELLER_DOMAINS = {
    "amazon.com": "amazon",
    "doordash.com": "doordash",
}

CARRIER_DOMAINS = {
    "fedex.com": "fedex",
    "ups.com": "ups",
    "usps.com": "usps",
    "dhl.com": "dhl",
}

SUPPORTED_DOMAINS = {**SELLER_DOMAINS, **CARRIER_DOMAINS}

AMAZON_ORDER_PATTERN = re.compile(r"\b\d{3}-\d{7}-\d{7}\b", re.IGNORECASE)
UPS_TRACKING_PATTERN = re.compile(r"\b1Z[0-9A-Z]{16}\b", re.IGNORECASE)
FEDEX_TRACKING_PATTERN = re.compile(r"\b\d{12,20}\b")
USPS_TRACKING_PATTERN = re.compile(r"\b(?:94|93|92|95)\d{20,22}\b")
DHL_TRACKING_PATTERN = re.compile(r"\b\d{10,11}\b")

STATUS_PATTERNS = [
    (re.compile(r"\bout for delivery\b", re.IGNORECASE), "out for delivery"),
    (re.compile(r"\bdelivered\b", re.IGNORECASE), "delivered"),
    (re.compile(r"\barriving overnight\b", re.IGNORECASE), "arriving overnight"),
    (re.compile(r"\barriving today\b", re.IGNORECASE), "arriving today"),
    (re.compile(r"\barriving tomorrow\b", re.IGNORECASE), "arriving tomorrow"),
    (re.compile(r"\bin transit\b", re.IGNORECASE), "in transit"),
    (re.compile(r"\bshipped\b", re.IGNORECASE), "shipped"),
]


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_domain(value: str | None) -> str | None:
    normalized = _normalize_text(value).lower()
    return normalized or None


def normalize_party(value: str | None) -> str | None:
    normalized = _normalize_text(value).lower()
    return normalized or None


def normalize_order_number(value: str | None) -> str | None:
    normalized = _normalize_text(value).upper()
    return normalized or None


def normalize_tracking_number(value: str | None) -> str | None:
    normalized = re.sub(r"[^0-9A-Z]", "", _normalize_text(value).upper())
    return normalized or None


class GmailShipmentEmailReconciler:
    def __init__(self, message_store: GmailMessageStore) -> None:
        self.message_store = message_store

    def process_message(self, account_id: str, message: GmailStoredMessage) -> GmailShipmentScrubResult:
        sender_domain = self._sender_domain(message)
        source_type = self._source_type(sender_domain)
        extracted_order_number, extracted_tracking_number = self._extract_identifiers(message)
        result = GmailShipmentScrubResult(
            reason_code="unsupported_domain",
            sender_domain=sender_domain,
            source_type=source_type,
            extracted_order_number=extracted_order_number,
            extracted_tracking_number=extracted_tracking_number,
        )

        if sender_domain not in SUPPORTED_DOMAINS:
            self._log_decision(message, result)
            return result

        records = self.message_store.list_shipment_records(account_id)
        if not records:
            result.reason_code = "no_existing_order"
            self._log_decision(message, result)
            return result

        matched_record, matched_by, reason_code = self._match_record(
            records=records,
            sender_domain=sender_domain,
            source_type=source_type,
            extracted_order_number=extracted_order_number,
            extracted_tracking_number=extracted_tracking_number,
        )
        if matched_record is None:
            result.reason_code = reason_code
            self._log_decision(message, result)
            return result

        result.action = "matched"
        result.reason_code = "matched_existing_order"
        result.matched_record_id = matched_record.record_id
        result.matched_by = matched_by

        updated_record, status_update_applied = self._apply_updates(
            record=matched_record,
            message=message,
            sender_domain=sender_domain,
            source_type=source_type,
            extracted_order_number=extracted_order_number,
            extracted_tracking_number=extracted_tracking_number,
        )
        if status_update_applied:
            self.message_store.upsert_shipment_record(updated_record)
            result.action = "updated"
            result.reason_code = "updated_existing_order"
            result.status_update_applied = True

        self._log_decision(message, result)
        return result

    def _sender_domain(self, message: GmailStoredMessage) -> str | None:
        _, sender_email = parseaddr(message.sender or "")
        if "@" not in sender_email:
            return None
        return normalize_domain(sender_email.rsplit("@", 1)[-1])

    def _source_type(self, sender_domain: str | None) -> str:
        if sender_domain in SELLER_DOMAINS:
            return "seller"
        if sender_domain in CARRIER_DOMAINS:
            return "carrier"
        return "unknown"

    def _message_text(self, message: GmailStoredMessage) -> str:
        subject = _normalize_text(message.subject)
        snippet = _normalize_text(message.snippet)
        return "\n".join(part for part in [subject, snippet] if part)

    def _extract_identifiers(self, message: GmailStoredMessage) -> tuple[str | None, str | None]:
        text = self._message_text(message)
        order_match = AMAZON_ORDER_PATTERN.search(text)
        order_number = normalize_order_number(order_match.group(0)) if order_match is not None else None

        tracking_number = None
        for pattern in (UPS_TRACKING_PATTERN, USPS_TRACKING_PATTERN, FEDEX_TRACKING_PATTERN, DHL_TRACKING_PATTERN):
            match = pattern.search(text)
            if match is not None:
                tracking_number = normalize_tracking_number(match.group(0))
                break
        return order_number, tracking_number

    def _extract_status(self, message: GmailStoredMessage) -> str | None:
        text = self._message_text(message)
        for pattern, status in STATUS_PATTERNS:
            if pattern.search(text):
                return status
        return None

    def _match_record(
        self,
        *,
        records: list[GmailShipmentRecord],
        sender_domain: str | None,
        source_type: str,
        extracted_order_number: str | None,
        extracted_tracking_number: str | None,
    ) -> tuple[GmailShipmentRecord | None, str | None, str]:
        if source_type == "carrier":
            if extracted_tracking_number is None:
                return None, None, "carrier_not_linked_to_existing_order"
            matches = [
                record
                for record in records
                if normalize_tracking_number(record.tracking_number) == extracted_tracking_number
                and (
                    normalize_party(record.carrier) == normalize_party(CARRIER_DOMAINS.get(sender_domain))
                    or normalize_domain(record.domain) == sender_domain
                )
            ]
            if len(matches) > 1:
                return None, None, "ambiguous_match"
            if matches:
                return matches[0], "tracking_number", "matched_existing_order"
            return None, None, "carrier_not_linked_to_existing_order"

        if extracted_tracking_number is not None:
            matches = [
                record for record in records if normalize_tracking_number(record.tracking_number) == extracted_tracking_number
            ]
            if len(matches) > 1:
                return None, None, "ambiguous_match"
            if matches:
                return matches[0], "tracking_number", "matched_existing_order"

        if extracted_order_number is not None:
            domain_matches = [
                record
                for record in records
                if normalize_order_number(record.order_number) == extracted_order_number
                and normalize_domain(record.domain) == sender_domain
            ]
            if len(domain_matches) > 1:
                return None, None, "ambiguous_match"
            if domain_matches:
                return domain_matches[0], "order_number_domain", "matched_existing_order"

            seller_name = SELLER_DOMAINS.get(sender_domain or "")
            seller_matches = [
                record
                for record in records
                if normalize_order_number(record.order_number) == extracted_order_number
                and normalize_party(record.seller) == normalize_party(seller_name)
            ]
            if len(seller_matches) > 1:
                return None, None, "ambiguous_match"
            if seller_matches:
                return seller_matches[0], "order_number_seller", "matched_existing_order"
            return None, None, "order_mismatch"

        return None, None, "tracking_mismatch"

    def _apply_updates(
        self,
        *,
        record: GmailShipmentRecord,
        message: GmailStoredMessage,
        sender_domain: str | None,
        source_type: str,
        extracted_order_number: str | None,
        extracted_tracking_number: str | None,
    ) -> tuple[GmailShipmentRecord, bool]:
        updates: dict[str, object] = {"last_seen_at": message.received_at}
        applied = False
        status = self._extract_status(message)
        if status and status != record.last_known_status:
            updates["last_known_status"] = status
            updates["status_updated_at"] = message.received_at
            applied = True
        if source_type == "carrier":
            canonical_carrier = CARRIER_DOMAINS.get(sender_domain or "")
            if canonical_carrier and not normalize_party(record.carrier):
                updates["carrier"] = canonical_carrier
                applied = True
        if source_type == "seller":
            canonical_seller = SELLER_DOMAINS.get(sender_domain or "")
            if canonical_seller and not normalize_party(record.seller):
                updates["seller"] = canonical_seller
                applied = True
        if extracted_tracking_number and not normalize_tracking_number(record.tracking_number) and source_type == "seller":
            updates["tracking_number"] = extracted_tracking_number
            applied = True
        if extracted_order_number and not normalize_order_number(record.order_number):
            updates["order_number"] = extracted_order_number
            applied = True
        if sender_domain and not normalize_domain(record.domain) and source_type == "seller":
            updates["domain"] = sender_domain
            applied = True
        updated_record = record.model_copy(update=updates)
        return updated_record, applied

    def _log_decision(self, message: GmailStoredMessage, result: GmailShipmentScrubResult) -> None:
        LOGGER.info(
            "Gmail shipment scrubber processed message",
            extra={
                "event_data": {
                    "message_id": message.message_id,
                    "sender_domain": result.sender_domain,
                    "source_type": result.source_type,
                    "action": result.action,
                    "reason_code": result.reason_code,
                    "matched_record_id": result.matched_record_id,
                    "matched_by": result.matched_by,
                }
            },
        )
