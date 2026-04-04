from __future__ import annotations

import quopri
import re
from datetime import datetime
from email.utils import parseaddr

from logging_utils import get_logger
from providers.gmail.order_hashing import stable_text_hash
from providers.gmail.order_validation import validate_phase1_payload
from providers.gmail.models import (
    GmailPhase1BodyAvailability,
    GmailPhase1DecodeState,
    GmailPhase1DiagnosticItem,
    GmailPhase1FetchedBody,
    GmailPhase1FetchedEmail,
    GmailPhase1NormalizationMetadata,
    GmailPhase1NormalizedEmail,
    GmailPhase1SenderIdentity,
)


LOGGER = get_logger(__name__)
BOUNDARY_PATTERN = re.compile(r'boundary="?([^";]+)"?', re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)
NORMALIZER_VERSION = "order-phase1-normalizer.v2"


class GmailOrderPhase1Error(RuntimeError):
    pass


class GmailOrderPhase1Processor:
    async def fetch_message(self, *, adapter, account_id: str, message_id: str) -> GmailPhase1FetchedEmail:
        try:
            payload = await adapter.fetch_full_message_payload(account_id, message_id)
        except Exception as exc:
            LOGGER.warning(
                "ORDER Phase 1 full-message fetch failed",
                extra={"event_data": {"account_id": account_id, "message_id": message_id, "detail": str(exc)}},
            )
            return GmailPhase1FetchedEmail(
                account_id=account_id,
                message_id=message_id,
                fetch_status="failed",
                fetch_error=str(exc),
                fetch_diagnostics=[str(exc)],
                mime_parse_status="failed",
                mime_diagnostics=["fetch failed before MIME parsing"],
            )
        fetched = self.package_fetched_email(account_id=account_id, payload=payload)
        log_method = LOGGER.info if fetched.fetch_status == "success" else LOGGER.warning
        log_method(
            "ORDER Phase 1 full-message fetch completed",
            extra={
                "event_data": {
                    "account_id": account_id,
                    "message_id": message_id,
                    "fetch_status": fetched.fetch_status,
                    "has_html": bool(self._body_content(fetched.html_body)),
                    "has_text": bool(self._body_content(fetched.text_body)),
                    "fetch_error": fetched.fetch_error,
                }
            },
        )
        return fetched

    def package_fetched_email(self, *, account_id: str, payload: dict[str, object]) -> GmailPhase1FetchedEmail:
        headers = self._normalize_headers(payload.get("headers"))
        text_body = self._package_body(payload.get("text_body"), mime_type="text/plain")
        html_body = self._package_body(payload.get("html_body"), mime_type="text/html")
        fetch_status = str(payload.get("fetch_status") or "success").strip().lower() or "success"
        if fetch_status not in {"success", "partial", "failed"}:
            fetch_status = "partial"
        fetch_error = str(payload.get("fetch_error") or "").strip() or None
        fetch_diagnostics = [str(item).strip() for item in payload.get("fetch_diagnostics") or [] if str(item).strip()]
        if text_body is None and html_body is None and fetch_status == "success":
            fetch_status = "partial"
            if not fetch_error:
                fetch_error = "gmail full message did not include text/plain or text/html body parts"
            if fetch_error not in fetch_diagnostics:
                fetch_diagnostics.append(fetch_error)
        mime_parse_status = str(payload.get("mime_parse_status") or "success").strip().lower() or "success"
        if mime_parse_status not in {"success", "partial", "failed"}:
            mime_parse_status = "failed"
        mime_diagnostics = [str(item).strip() for item in payload.get("mime_diagnostics") or [] if str(item).strip()]
        mime_boundaries = [str(item).strip() for item in payload.get("mime_boundaries") or [] if str(item).strip()]
        part_inventory = [item for item in payload.get("part_inventory") or [] if isinstance(item, dict)]
        fetched = GmailPhase1FetchedEmail(
            account_id=account_id,
            message_id=str(payload.get("message_id") or "").strip(),
            thread_id=self._optional_string(payload.get("thread_id")),
            message_id_header=headers.get("message-id"),
            subject=self._optional_string(payload.get("subject")) or headers.get("subject"),
            sender=self._optional_string(payload.get("sender")) or headers.get("from"),
            date=self._optional_string(payload.get("date")) or headers.get("date"),
            received_at=payload.get("received_at"),
            headers=headers,
            text_body=text_body,
            html_body=html_body,
            fetch_status=fetch_status,
            fetch_error=fetch_error,
            fetch_diagnostics=fetch_diagnostics,
            mime_parse_status=mime_parse_status,
            mime_diagnostics=mime_diagnostics,
            mime_boundaries=mime_boundaries,
            part_inventory=part_inventory,
        )
        return fetched

    def normalize_fetched_email(self, fetched: GmailPhase1FetchedEmail) -> GmailPhase1NormalizedEmail:
        sender_identity = self.normalize_sender(fetched.sender)
        sender_status, sender_diagnostics = self._sender_status(sender_identity)
        raw_html = self._body_content(fetched.html_body)
        raw_text = self._body_content(fetched.text_body)
        decoded_html, html_diagnostics = self.decode_body(
            raw_html,
            transfer_encoding=self._body_transfer_encoding(fetched.html_body),
            charset=self._body_charset(fetched.html_body),
        )
        decoded_text, text_diagnostics = self.decode_body(
            raw_text,
            transfer_encoding=self._body_transfer_encoding(fetched.text_body),
            charset=self._body_charset(fetched.text_body),
        )
        decode_diagnostics = html_diagnostics + text_diagnostics
        if not raw_html and not raw_text:
            decode_status = "failed"
            decode_diagnostics.append("no body content was available to decode")
        elif any(diag.startswith("failed:") for diag in decode_diagnostics):
            decode_status = "partial" if any(value for value in [decoded_html, decoded_text]) else "failed"
        elif any(diag.startswith("fallback:") for diag in decode_diagnostics):
            decode_status = "partial"
        else:
            decode_status = "success"
        decoded_html_quality = self._score_body_quality(decoded_html, body_type="html")
        decoded_text_quality = self._score_body_quality(decoded_text, body_type="text")

        selected_body_type, selected_body_content, selected_body_quality, selection_reason = self.select_preferred_body_source(
            decoded_html=decoded_html,
            decoded_text=decoded_text,
        )
        selected_body_source, selected_body_selection_path = self._selection_provenance(
            fetched=fetched,
            selected_body_type=selected_body_type,
            selected_body_quality=selected_body_quality,
        )
        body_availability = GmailPhase1BodyAvailability(
            html_available=bool(decoded_html),
            text_available=bool(decoded_text),
            html_length=len(decoded_html or ""),
            text_length=len(decoded_text or ""),
        )
        transfer_encodings = [
            self._body_transfer_encoding(fetched.html_body),
            self._body_transfer_encoding(fetched.text_body),
        ]
        mime_boundaries = list(dict.fromkeys(fetched.mime_boundaries + [
            boundary
            for boundary in [self._body_boundary(fetched.html_body), self._body_boundary(fetched.text_body)]
            if boundary
        ]))
        body_selection_status = "success" if selected_body_content else "failed"
        if selected_body_quality in {"fallback_text", "corrupted"}:
            body_selection_status = "partial"
        normalized = GmailPhase1NormalizedEmail(
            message_id=fetched.message_id,
            thread_id=fetched.thread_id,
            provider_message_id=fetched.message_id,
            provider_thread_id=fetched.thread_id,
            rfc_message_id=fetched.message_id_header,
            subject=fetched.headers.get("subject") or fetched.subject,
            sender_name=sender_identity.sender_name,
            sender_email=sender_identity.sender_email,
            sender_domain=sender_identity.sender_domain,
            raw_sender=sender_identity.raw_sender,
            received_at=fetched.received_at,
            raw_html=raw_html,
            raw_text=raw_text,
            headers=fetched.headers,
            fetch_status=fetched.fetch_status,
            fetch_error=fetched.fetch_error,
            fetch_diagnostics=fetched.fetch_diagnostics,
            mime_parse_status=fetched.mime_parse_status,
            mime_diagnostics=fetched.mime_diagnostics,
            sender_normalization_status=sender_status,
            sender_diagnostics=sender_diagnostics,
            content_transfer_encoding=next((value for value in transfer_encodings if value), None),
            mime_boundaries=mime_boundaries,
            mime_parts=fetched.part_inventory,
            part_inventory=fetched.part_inventory,
            body_availability=body_availability,
            decoded_html=decoded_html,
            decoded_text=decoded_text,
            decoded_html_quality=decoded_html_quality,
            decoded_text_quality=decoded_text_quality,
            decode_state=GmailPhase1DecodeState(status=decode_status, diagnostics=decode_diagnostics),
            selected_body_type=selected_body_type,
            selected_body_content=selected_body_content,
            selected_body_quality=selected_body_quality,
            body_selection_status=body_selection_status,
            body_selection_reason=selection_reason,
            selected_body_reason=selection_reason,
            selected_body_source=selected_body_source,
            selected_body_selection_path=selected_body_selection_path,
            raw_html_hash=stable_text_hash(raw_html),
            raw_text_hash=stable_text_hash(raw_text),
            decoded_html_hash=stable_text_hash(decoded_html),
            decoded_text_hash=stable_text_hash(decoded_text),
            selected_body_hash=stable_text_hash(selected_body_content),
            stage_diagnostics=self._stage_diagnostics(
                fetch=fetched.fetch_diagnostics,
                mime=fetched.mime_diagnostics,
                sender=sender_diagnostics,
                decode=decode_diagnostics,
                body_selection=[] if selection_reason is None else [selection_reason],
                validation=[],
            ),
            normalization_metadata=GmailPhase1NormalizationMetadata(
                normalizer_version=NORMALIZER_VERSION,
                decode_strategy="quoted_printable_bytes_then_charset_decode",
                mime_parse_status=fetched.mime_parse_status,
                body_selection_strategy="quality_rank_with_fallback",
                normalized_at=datetime.now().astimezone(),
            ),
        )
        validation_status, handoff_ready, validation_diagnostics = validate_phase1_payload(normalized)
        stage_diagnostics = dict(normalized.stage_diagnostics)
        stage_diagnostics["validation"] = self._diagnostic_items(validation_diagnostics)
        return normalized.model_copy(
            update={
                "handoff_ready": handoff_ready,
                "validation_status": validation_status,
                "validation_diagnostics": validation_diagnostics,
                "stage_diagnostics": stage_diagnostics,
            }
        )

    async def fetch_and_normalize_message(self, *, adapter, account_id: str, message_id: str) -> GmailPhase1NormalizedEmail:
        fetched = await self.fetch_message(adapter=adapter, account_id=account_id, message_id=message_id)
        normalized = self.normalize_fetched_email(fetched)
        LOGGER.info(
            "ORDER Phase 1 normalization stage completed",
            extra={
                "event_data": {
                    "account_id": account_id,
                    "message_id": message_id,
                    "fetch_status": normalized.fetch_status,
                    "decode_status": normalized.decode_state.status,
                    "selected_body_type": normalized.selected_body_type,
                    "html_available": normalized.body_availability.html_available,
                    "text_available": normalized.body_availability.text_available,
                }
            },
        )
        return normalized

    def normalize_sender(self, raw_sender: str | None) -> GmailPhase1SenderIdentity:
        sender_value = self._optional_string(raw_sender)
        if not sender_value:
            return GmailPhase1SenderIdentity(raw_sender=raw_sender)
        display_name, parsed_email = parseaddr(sender_value)
        normalized_email = self._normalize_email(parsed_email)
        if normalized_email is None:
            email_match = EMAIL_PATTERN.search(sender_value)
            normalized_email = self._normalize_email(email_match.group(1) if email_match else None)
        sender_name = " ".join(display_name.split()).strip() or None
        if sender_name is None and normalized_email is None:
            sender_name = sender_value.strip(" <>\"'") or None
        sender_domain = normalized_email.rsplit("@", 1)[-1] if normalized_email and "@" in normalized_email else None
        return GmailPhase1SenderIdentity(
            raw_sender=raw_sender,
            sender_name=sender_name,
            sender_email=normalized_email,
            sender_domain=sender_domain,
        )

    def decode_body(
        self,
        raw_value: str | None,
        *,
        transfer_encoding: str | None,
        charset: str | None,
    ) -> tuple[str | None, list[str]]:
        if raw_value is None:
            return None, []
        normalized_raw = raw_value.replace("\r\n", "\n").replace("\r", "\n")
        encoding = str(transfer_encoding or "").strip().lower()
        diagnostics: list[str] = []
        try:
            if encoding == "quoted-printable" or self._looks_like_quoted_printable(normalized_raw, transfer_encoding=encoding):
                source_bytes = normalized_raw.encode("latin-1", errors="ignore")
                decoded_bytes = quopri.decodestring(source_bytes)
            else:
                decoded_bytes = normalized_raw.encode("latin-1", errors="ignore")
        except Exception as exc:
            diagnostics.append(f"failed:{exc}")
            return normalized_raw, diagnostics
        decoded, decode_diagnostics = self._decode_bytes(decoded_bytes, charset=charset)
        diagnostics.extend(decode_diagnostics)
        if "\ufffd" in decoded:
            diagnostics.append("fallback:replacement_characters_present")
        return decoded.replace("\r\n", "\n").replace("\r", "\n"), diagnostics

    def select_preferred_body_source(
        self,
        *,
        decoded_html: str | None,
        decoded_text: str | None,
    ) -> tuple[str, str | None, str, str]:
        html_value = self._optional_string(decoded_html)
        text_value = self._optional_string(decoded_text)
        html_quality = self._score_body_quality(html_value, body_type="html")
        text_quality = self._score_body_quality(text_value, body_type="text")
        quality_rank = {
            "rich_html": 5,
            "usable_html": 4,
            "usable_text": 3,
            "fallback_text": 2,
            "corrupted": 1,
            "empty": 0,
        }
        if quality_rank[html_quality] >= quality_rank[text_quality] and html_quality not in {"empty", "corrupted"}:
            return "html", html_value, html_quality, f"selected html because quality={html_quality}"
        if text_quality not in {"empty", "corrupted"}:
            return "text", text_value, text_quality, f"selected text because quality={text_quality}"
        if html_value:
            return "html", html_value, html_quality, f"selected html fallback because quality={html_quality}"
        if text_value:
            return "text", text_value, text_quality, f"selected text fallback because quality={text_quality}"
        return "none", None, "empty", "no usable decoded body content"

    def _package_body(self, payload: object, *, mime_type: str) -> GmailPhase1FetchedBody | None:
        if not isinstance(payload, dict):
            return None
        content = self._optional_string(payload.get("content"))
        headers = self._normalize_headers(payload.get("headers"))
        return GmailPhase1FetchedBody(
            mime_type=mime_type,  # type: ignore[arg-type]
            content=content,
            headers=headers,
            content_transfer_encoding=self._optional_string(payload.get("content_transfer_encoding"))
            or headers.get("content-transfer-encoding"),
            charset=self._optional_string(payload.get("charset")) or self._extract_charset(headers),
            mime_boundary=self._optional_string(payload.get("mime_boundary")) or self._extract_boundary(headers),
        )

    @staticmethod
    def _normalize_headers(headers: object) -> dict[str, str]:
        if not isinstance(headers, dict):
            return {}
        normalized: dict[str, str] = {}
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            normalized[key.strip().lower()] = value
        return normalized

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _normalize_email(value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().strip("<>").strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            return None
        return normalized

    @staticmethod
    def _body_content(body: GmailPhase1FetchedBody | None) -> str | None:
        if body is None:
            return None
        return body.content

    @staticmethod
    def _body_transfer_encoding(body: GmailPhase1FetchedBody | None) -> str | None:
        if body is None:
            return None
        return body.content_transfer_encoding

    @staticmethod
    def _body_charset(body: GmailPhase1FetchedBody | None) -> str | None:
        if body is None:
            return None
        return body.charset

    @staticmethod
    def _body_boundary(body: GmailPhase1FetchedBody | None) -> str | None:
        if body is None:
            return None
        return body.mime_boundary

    @staticmethod
    def _extract_boundary(headers: dict[str, str]) -> str | None:
        content_type = str(headers.get("content-type") or "").strip()
        if not content_type:
            return None
        match = BOUNDARY_PATTERN.search(content_type)
        if match is None:
            return None
        return match.group(1).strip() or None

    @staticmethod
    def _extract_charset(headers: dict[str, str]) -> str | None:
        content_type = str(headers.get("content-type") or "").strip()
        if not content_type:
            return None
        match = re.search(r'charset="?([^";]+)"?', content_type, re.IGNORECASE)
        if match is None:
            return None
        return match.group(1).strip() or None

    def _looks_like_quoted_printable(self, value: str, *, transfer_encoding: str) -> bool:
        if transfer_encoding == "quoted-printable":
            return True
        if "=\n" in value or "=\r\n" in value:
            return True
        lines = [line for line in value.splitlines() if line.strip()]
        if not lines:
            return False
        qp_hits = sum(1 for line in lines if re.search(r"=[0-9A-Fa-f]{2}(?:[^0-9A-Fa-f]|$)", line))
        return qp_hits > 0 and qp_hits >= max(2, len(lines) // 4)

    @staticmethod
    def _decode_bytes(value: bytes, *, charset: str | None) -> tuple[str, list[str]]:
        diagnostics: list[str] = []
        candidates = []
        if charset:
            candidates.append(charset.strip())
        candidates.extend(["utf-8", "latin-1"])
        seen: set[str] = set()
        for candidate in candidates:
            normalized = candidate.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            try:
                decoded = value.decode(candidate)
                if candidate.lower() != "utf-8":
                    diagnostics.append(f"fallback:decoded_with_{candidate.lower()}")
                return decoded, diagnostics
            except Exception:
                continue
        diagnostics.append("failed:unable_to_decode_bytes")
        return value.decode("utf-8", errors="replace"), diagnostics

    @staticmethod
    def _score_body_quality(value: str | None, *, body_type: str) -> str:
        text = str(value or "")
        stripped = text.strip()
        if not stripped:
            return "empty"
        if "\ufffd" in stripped:
            return "corrupted"
        placeholder_patterns = (
            "your client does not support html",
            "your browser does not support html",
            "view this email in your browser",
        )
        if any(pattern in stripped.lower() for pattern in placeholder_patterns):
            return "fallback_text"
        if body_type == "html" and "<" in stripped and ">" in stripped:
            if len(stripped) >= 120 or any(tag in stripped.lower() for tag in ("<html", "<body", "<table", "<div", "<p", "<strong")):
                return "rich_html"
            return "usable_html"
        if len(stripped) < 40:
            return "fallback_text"
        return "usable_text"

    @staticmethod
    def _sender_status(sender_identity: GmailPhase1SenderIdentity) -> tuple[str, list[str]]:
        diagnostics: list[str] = []
        if not sender_identity.raw_sender:
            diagnostics.append("raw sender is missing")
        if sender_identity.raw_sender and not (sender_identity.sender_name or sender_identity.sender_email):
            diagnostics.append("sender could not be normalized from raw sender")
        if sender_identity.raw_sender and sender_identity.sender_email is None:
            diagnostics.append("sender email could not be derived from raw sender")
        if sender_identity.sender_email and not sender_identity.sender_domain:
            diagnostics.append("sender domain could not be derived from sender email")
        if not diagnostics:
            return "success", diagnostics
        if sender_identity.raw_sender:
            return "partial", diagnostics
        return "failed", diagnostics

    @staticmethod
    def _diagnostic_code(detail: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", detail.strip().lower()).strip("_")
        return normalized or "diagnostic"

    def _diagnostic_items(self, diagnostics: list[str]) -> list[GmailPhase1DiagnosticItem]:
        return [GmailPhase1DiagnosticItem(code=self._diagnostic_code(detail), detail=detail) for detail in diagnostics]

    def _stage_diagnostics(
        self,
        *,
        fetch: list[str],
        mime: list[str],
        sender: list[str],
        decode: list[str],
        body_selection: list[str],
        validation: list[str],
    ) -> dict[str, list[GmailPhase1DiagnosticItem]]:
        return {
            "fetch": self._diagnostic_items(fetch),
            "mime_parse": self._diagnostic_items(mime),
            "sender_normalization": self._diagnostic_items(sender),
            "decode": self._diagnostic_items(decode),
            "body_selection": self._diagnostic_items(body_selection),
            "validation": self._diagnostic_items(validation),
        }

    def _selection_provenance(
        self,
        *,
        fetched: GmailPhase1FetchedEmail,
        selected_body_type: str,
        selected_body_quality: str,
    ) -> tuple[str | None, str | None]:
        if selected_body_type == "html":
            source = "parsed_mime_html_part" if fetched.html_body is not None else "fallback_body_extraction_path"
        elif selected_body_type == "text":
            source = "parsed_mime_text_part" if fetched.text_body is not None else "fallback_body_extraction_path"
        else:
            return None, "no_usable_content"
        if selected_body_quality in {"rich_html", "usable_html", "usable_text"}:
            return source, "quality_comparison"
        return source, "fallback_logic"
