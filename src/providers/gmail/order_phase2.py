from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

from providers.gmail.models import (
    GmailPhase1DiagnosticItem,
    GmailPhase1NormalizedEmail,
    GmailPhase1Reference,
    GmailPhase2Link,
    GmailPhase2Metrics,
    GmailPhase2NormalizationMetadata,
    GmailPhase2ScrubbedEmail,
    GmailPhase2WorkingEmail,
)
from providers.gmail.order_html_extractor import extract_visible_text_from_html
from providers.gmail.order_scrubber_rules import (
    CHROME_LINE_PATTERNS,
    FILLER_ENTITY_PATTERNS,
    FOOTER_CUTOFF_PATTERNS,
    IGNORE_LINE_PATTERNS,
    IMPORTANT_LINK_PATTERNS,
    PROMO_MARKER_PATTERNS,
    STOP_MARKER_PATTERNS,
    TRACKING_HOST_PATTERNS,
    TRANSACTIONAL_ANCHOR_PATTERNS,
)


SCRUBBER_VERSION = "order-phase2-scrubber.v1"
URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
ORDER_ID_PATTERN = re.compile(r"\b(?:order|reference)\s*(?:#|number|no\.?)?\s*:?\s*([A-Z0-9-]{6,})\b", re.IGNORECASE)
BARE_ORDER_ID_PATTERN = re.compile(r"\b\d{3}-\d{7}-\d{7}\b")
STATUS_PATTERN = re.compile(r"\b(arriving|ordered|confirmed|shipped|delivered|out for delivery|ready for pickup|pickup)\b", re.IGNORECASE)
GREETING_PATTERN = re.compile(r"\b(thanks for your order|thank you for your order|order confirmation)\b", re.IGNORECASE)
ITEM_PATTERN = re.compile(r"(^\*|\bitem\b|\bboard\b|\bdevelopment\b|\bmeta quest\b|\bazelaic\b)", re.IGNORECASE)
QUANTITY_PATTERN = re.compile(r"\bquantity\b", re.IGNORECASE)
TOTAL_PATTERN = re.compile(r"\b(grand total|order total|total)\b", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"(?:(?:usd|\$)\s*\d|\d+(?:\.\d{2})?\s*(?:usd|\$))", re.IGNORECASE)
ACTION_LINK_PATTERN = re.compile(r"\b(view or edit order|order details|track package|track your package)\b", re.IGNORECASE)


class GmailOrderPhase2Scrubber:
    def scrub(self, phase1: GmailPhase1NormalizedEmail) -> GmailPhase2ScrubbedEmail:
        phase1_reference = self._phase1_reference(phase1)
        working = self.build_working_object(phase1)
        if working is None:
            diagnostics = ["phase1 payload is not ready for handoff"]
            return GmailPhase2ScrubbedEmail(
                phase1_reference=phase1_reference,
                message_id=phase1.message_id,
                thread_id=phase1.thread_id,
                provider_message_id=phase1.provider_message_id,
                provider_thread_id=phase1.provider_thread_id,
                rfc_message_id=phase1.rfc_message_id,
                subject=phase1.subject,
                sender_name=phase1.sender_name,
                sender_email=phase1.sender_email,
                sender_domain=phase1.sender_domain,
                selected_body_type=phase1.selected_body_type,
                selected_body_source=phase1.selected_body_source,
                selected_body_selection_path=phase1.selected_body_selection_path,
                scrub_status="failed",
                scrub_diagnostics=diagnostics,
                stage_statuses={
                    "intake": "failed",
                    "content_extraction": "failed",
                    "hidden_content": "failed",
                    "chrome_removal": "failed",
                    "footer_cutoff": "failed",
                    "line_normalization": "failed",
                    "link_extraction": "failed",
                },
                stage_diagnostics={name: self._diagnostics(diagnostics) for name in (
                    "intake",
                    "content_extraction",
                    "hidden_content",
                    "chrome_removal",
                    "footer_cutoff",
                    "line_normalization",
                    "link_extraction",
                )},
                normalization_metadata=GmailPhase2NormalizationMetadata(
                    scrubber_version=SCRUBBER_VERSION,
                    source_strategy="handoff_guardrail",
                    body_input_type=phase1.selected_body_type,
                    normalized_at=datetime.now().astimezone(),
                ),
            )

        stage_statuses = dict(working.stage_statuses)
        stage_diagnostics = dict(working.stage_diagnostics)
        applied_rules = list(working.applied_rules)
        extracted_links = list(working.extracted_links)

        content_text = working.selected_transactional_text or working.visible_text or working.source_text or ""
        content_extraction_diagnostics = stage_diagnostics.get("content_extraction", [])
        hidden_removed = any("hidden html nodes" in item.detail for item in content_extraction_diagnostics)
        hidden_diagnostics: list[str] = []
        content_text, hidden_rule_hits = self.strip_hidden_content(content_text)
        if hidden_rule_hits:
            hidden_removed = True
            hidden_diagnostics.extend(hidden_rule_hits)
            applied_rules.extend(hidden_rule_hits)
            stage_statuses["hidden_content"] = "partial"
        else:
            stage_statuses["hidden_content"] = "success"
        stage_diagnostics["hidden_content"] = self._diagnostics(hidden_diagnostics)

        lines = content_text.splitlines()
        lines, chrome_hits, chrome_removed = self.remove_email_chrome(lines)
        if chrome_hits:
            applied_rules.extend(chrome_hits)
        stage_statuses["chrome_removal"] = "partial" if chrome_removed else "success"
        stage_diagnostics["chrome_removal"] = self._diagnostics(chrome_hits)

        lines, cutoff_rule = self.apply_footer_cutoff(lines)
        if cutoff_rule is not None:
            applied_rules.append(cutoff_rule)
        stage_statuses["footer_cutoff"] = "partial" if cutoff_rule else "success"
        stage_diagnostics["footer_cutoff"] = self._diagnostics([] if cutoff_rule is None else [cutoff_rule])

        lines, ignore_hits, removed_count = self.apply_seller_agnostic_rules(lines)
        if ignore_hits:
            applied_rules.extend(ignore_hits)
        lines, promo_hits = self.suppress_recommendation_lines(lines)
        if promo_hits:
            applied_rules.extend(promo_hits)
        stage_statuses["line_normalization"] = "success"
        normalized_lines = self.normalize_semantic_lines(lines)
        scrubbed_text = "\n".join(normalized_lines).strip()
        stage_diagnostics["line_normalization"] = self._diagnostics(ignore_hits + promo_hits)

        extracted_links = self._prioritize_links(self._merge_links(extracted_links, self.extract_links_from_text(content_text)))
        stage_statuses["link_extraction"] = "success"
        stage_diagnostics["link_extraction"] = self._diagnostics(
            [] if not extracted_links else [f"extracted {len(extracted_links)} links"]
        )

        scrub_diagnostics = [
            detail.detail
            for items in stage_diagnostics.values()
            for detail in items
            if detail.detail
        ]
        transactional_quality, completeness_diagnostics = self._transactional_completeness(normalized_lines)
        scrub_diagnostics.extend(completeness_diagnostics)
        if not scrubbed_text:
            scrub_status = "failed"
        elif transactional_quality == "failed" and self._is_likely_transactional_email(working.selected_transactional_text or content_text):
            scrub_status = "failed"
        elif transactional_quality == "success":
            scrub_status = "success"
        else:
            scrub_status = "partial" if scrubbed_text else "failed"
        if not scrubbed_text:
            scrub_diagnostics.append("scrubbed text is empty")
        metrics = GmailPhase2Metrics(
            input_char_count=len(working.selected_body_content or ""),
            output_char_count=len(scrubbed_text),
            reduction_ratio=self._reduction_ratio(len(working.selected_body_content or ""), len(scrubbed_text)),
            input_line_count=len([line for line in (working.source_text or "").splitlines() if line.strip()]),
            output_line_count=len([line for line in normalized_lines if line.strip()]),
            lines_removed=max(0, len((working.source_text or "").splitlines()) - len(normalized_lines)) + removed_count,
            links_extracted=len(extracted_links),
            cutoff_rules_triggered=1 if cutoff_rule else 0,
            applied_rule_count=len(list(dict.fromkeys(applied_rules))),
        )
        return GmailPhase2ScrubbedEmail(
            phase1_reference=phase1_reference,
            message_id=working.message_id,
            thread_id=working.thread_id,
            provider_message_id=working.provider_message_id,
            provider_thread_id=working.provider_thread_id,
            rfc_message_id=working.rfc_message_id,
            subject=working.subject,
            sender_name=working.sender_name,
            sender_email=working.sender_email,
            sender_domain=working.sender_domain,
            selected_body_type=working.selected_body_type,
            selected_body_source=working.selected_body_source,
            selected_body_selection_path=working.selected_body_selection_path,
            scrubbed_text=scrubbed_text,
            normalized_lines=normalized_lines,
            extracted_links=extracted_links,
            applied_rules=list(dict.fromkeys(applied_rules)),
            hidden_content_stripped=hidden_removed,
            scrub_status=scrub_status,
            scrub_diagnostics=list(dict.fromkeys(scrub_diagnostics)),
            transactional_quality=transactional_quality,
            stage_statuses=stage_statuses,
            stage_diagnostics=stage_diagnostics,
            scrub_metrics=metrics,
            normalization_metadata=GmailPhase2NormalizationMetadata(
                scrubber_version=SCRUBBER_VERSION,
                source_strategy="html_visible_text" if working.selected_body_type == "html" else "plain_text_normalization",
                body_input_type=working.selected_body_type,
                normalized_at=datetime.now().astimezone(),
            ),
        )

    def build_working_object(self, phase1: GmailPhase1NormalizedEmail) -> GmailPhase2WorkingEmail | None:
        if not phase1.handoff_ready:
            return None
        if not phase1.selected_body_content or phase1.selected_body_type == "none":
            return None

        stage_statuses: dict[str, str] = {"intake": "success"}
        stage_diagnostics = {"intake": self._diagnostics([])}
        extracted_links: list[GmailPhase2Link] = []

        if phase1.selected_body_type == "html":
            visible_text, html_links, html_metrics = extract_visible_text_from_html(phase1.selected_body_content)
            source_text = visible_text
            visible_text_value = visible_text
            extracted_links = html_links
            content_diagnostics = []
            if html_metrics["hidden_nodes_removed"] > 0:
                content_diagnostics.append(f"removed {html_metrics['hidden_nodes_removed']} hidden html nodes")
            if html_metrics["tracking_images_removed"] > 0:
                content_diagnostics.append(f"removed {html_metrics['tracking_images_removed']} tracking images")
        else:
            source_text = self.normalize_plain_text(phase1.selected_body_content)
            visible_text_value = None
            content_diagnostics = []

        fallback_text = self.normalize_plain_text(phase1.decoded_text or phase1.raw_text or "") if phase1.decoded_text or phase1.raw_text else ""
        transactional_text, targeting_diagnostics, targeting_rules, targeting_status = self.select_transactional_content(
            primary_text=source_text or "",
            fallback_text=fallback_text,
        )
        content_diagnostics.extend(targeting_diagnostics)
        stage_statuses["transactional_targeting"] = targeting_status
        stage_diagnostics["transactional_targeting"] = self._diagnostics(targeting_diagnostics)
        stage_statuses["content_extraction"] = "success" if source_text else "partial"
        stage_diagnostics["content_extraction"] = self._diagnostics(content_diagnostics)

        return GmailPhase2WorkingEmail(
            phase1_reference=self._phase1_reference(phase1),
            message_id=phase1.message_id,
            thread_id=phase1.thread_id,
            provider_message_id=phase1.provider_message_id,
            provider_thread_id=phase1.provider_thread_id,
            rfc_message_id=phase1.rfc_message_id,
            subject=phase1.subject,
            sender_name=phase1.sender_name,
            sender_email=phase1.sender_email,
            sender_domain=phase1.sender_domain,
            selected_body_type=phase1.selected_body_type,
            selected_body_source=phase1.selected_body_source,
            selected_body_selection_path=phase1.selected_body_selection_path,
            selected_body_content=phase1.selected_body_content,
            source_text=source_text,
            visible_text=visible_text_value,
            normalized_text=transactional_text or source_text,
            transactional_candidates=[candidate for candidate in [source_text, fallback_text] if candidate],
            selected_transactional_text=transactional_text or source_text,
            extracted_links=self._prioritize_links(extracted_links),
            applied_rules=targeting_rules,
            stage_statuses=stage_statuses,  # type: ignore[arg-type]
            stage_diagnostics=stage_diagnostics,
        )

    def select_transactional_content(
        self,
        *,
        primary_text: str,
        fallback_text: str,
    ) -> tuple[str, list[str], list[str], str]:
        candidates = [
            ("primary", self._split_into_blocks(primary_text)),
            ("fallback", self._split_into_blocks(fallback_text)),
        ]
        best_text = ""
        best_source_name = "primary"
        best_blocks: list[str] = []
        best_index = 0
        best_score = -10_000
        diagnostics: list[str] = []
        applied_rules: list[str] = []
        best_reasons: list[str] = []
        best_merge_diagnostics: list[str] = []
        best_merge_rules: list[str] = []
        for source_name, blocks in candidates:
            for index, block in enumerate(blocks):
                seed_score, reasons = self._score_transactional_block(block)
                expanded_text, merge_diagnostics, merge_rules = self._expand_supporting_blocks(blocks, index)
                merged_score, merged_reasons = self._score_transactional_block(expanded_text)
                score = max(seed_score, merged_score)
                if score > best_score:
                    best_score = score
                    best_text = expanded_text
                    best_source_name = source_name
                    best_blocks = blocks
                    best_index = index
                    best_reasons = merged_reasons or reasons
                    best_merge_diagnostics = merge_diagnostics
                    best_merge_rules = merge_rules
                    diagnostics = [f"selected {source_name} transactional block {index} score={score} (seed={seed_score}, merged={merged_score})"] + best_reasons
        if best_text:
            diagnostics.extend(best_merge_diagnostics)
            applied_rules.append("transactional_targeting:selected_best_block")
            applied_rules.extend(best_merge_rules)
            if best_reasons:
                applied_rules.extend(f"transactional_targeting:{reason}" for reason in best_reasons)
            status = "success" if best_score >= 6 else "partial"
            return best_text, diagnostics, applied_rules, status
        return primary_text or fallback_text, ["transactional targeting fell back to raw extracted content"], applied_rules, "partial"

    def normalize_plain_text(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"=\n", "", normalized)
        lines = [line.strip() for line in normalized.splitlines()]
        rebuilt: list[str] = []
        for line in lines:
            if not line:
                rebuilt.append("")
                continue
            if rebuilt and rebuilt[-1] and self._should_join_wrapped_line(rebuilt[-1], line):
                rebuilt[-1] = f"{rebuilt[-1]} {line}".strip()
            else:
                rebuilt.append(line)
        compact = "\n".join(rebuilt)
        compact = re.sub(r"\n{3,}", "\n\n", compact)
        return compact.strip()

    def strip_hidden_content(self, text: str) -> tuple[str, list[str]]:
        updated = text
        applied: list[str] = []
        for pattern in FILLER_ENTITY_PATTERNS:
            if pattern.search(updated):
                updated = pattern.sub(" ", updated)
                applied.append(f"hidden_content:{pattern.pattern}")
        updated = "\n".join(
            line for line in updated.splitlines()
            if not self._looks_like_hidden_preheader(line)
        ).strip()
        return updated, applied

    def remove_email_chrome(self, lines: list[str]) -> tuple[list[str], list[str], bool]:
        kept: list[str] = []
        hits: list[str] = []
        removed = False
        for line in lines:
            stripped = line.strip()
            if stripped and any(pattern.search(stripped) for pattern in CHROME_LINE_PATTERNS):
                hits.append(f"chrome:{stripped.lower()}")
                removed = True
                continue
            kept.append(line)
        return kept, hits, removed

    def apply_footer_cutoff(self, lines: list[str]) -> tuple[list[str], str | None]:
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if any(pattern.search(stripped) for pattern in STOP_MARKER_PATTERNS + FOOTER_CUTOFF_PATTERNS + PROMO_MARKER_PATTERNS):
                return lines[:index], f"cutoff:{stripped[:80]}"
        return lines, None

    def apply_seller_agnostic_rules(self, lines: list[str]) -> tuple[list[str], list[str], int]:
        kept: list[str] = []
        hits: list[str] = []
        removed_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                kept.append("")
                continue
            if any(pattern.search(stripped) for pattern in IGNORE_LINE_PATTERNS):
                hits.append(f"ignore:{stripped.lower()}")
                removed_count += 1
                continue
            kept.append(stripped)
        return kept, hits, removed_count

    def suppress_recommendation_lines(self, lines: list[str]) -> tuple[list[str], list[str]]:
        kept: list[str] = []
        hits: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                kept.append(line)
                continue
            if any(pattern.search(stripped) for pattern in PROMO_MARKER_PATTERNS):
                hits.append(f"promo_suppressed:{stripped.lower()[:80]}")
                continue
            if re.search(r"-\d+%\s+\$\d", stripped):
                hits.append(f"promo_suppressed:{stripped.lower()[:80]}")
                continue
            kept.append(line)
        return kept, hits

    def normalize_semantic_lines(self, lines: list[str]) -> list[str]:
        normalized_lines: list[str] = []
        for raw_line in lines:
            line = " ".join(raw_line.strip().split())
            line = re.sub(r"\s+([:;,.!?])", r"\1", line)
            if not line:
                if normalized_lines and normalized_lines[-1] != "":
                    normalized_lines.append("")
                continue
            if self._low_value_line(line):
                continue
            if any(pattern.search(line) for pattern in PROMO_MARKER_PATTERNS):
                continue
            normalized_lines.append(line)
        normalized_lines = self._coalesce_semantic_lines(normalized_lines)
        while normalized_lines and normalized_lines[-1] == "":
            normalized_lines.pop()
        compact: list[str] = []
        for line in normalized_lines:
            if line == "" and compact and compact[-1] == "":
                continue
            compact.append(line)
        return compact

    def extract_links_from_text(self, text: str) -> list[GmailPhase2Link]:
        links: list[GmailPhase2Link] = []
        context_order_id = self._first_order_identifier(text)
        lines = text.splitlines()
        for index, line in enumerate(lines[:-1]):
            if not line.strip():
                continue
            next_line = lines[index + 1].strip()
            if next_line.lower().startswith("http"):
                repaired = self._repair_order_action_url(next_line, context_order_id)
                links.append(self._build_link(url=repaired, raw_url=next_line, label=line.strip(), source="plain_text"))
        for match in URL_PATTERN.finditer(text):
            url = match.group(0).rstrip(".,)")
            repaired = self._repair_order_action_url(url, context_order_id)
            links.append(self._build_link(url=repaired, raw_url=url, label=None, source="plain_text"))
        return links

    @staticmethod
    def _merge_links(primary: list[GmailPhase2Link], secondary: list[GmailPhase2Link]) -> list[GmailPhase2Link]:
        merged: list[GmailPhase2Link] = []
        seen: set[tuple[str, str | None]] = set()
        for item in primary + secondary:
            key = ((item.normalized_url or item.url), item.label)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    @staticmethod
    def _should_join_wrapped_line(previous: str, current: str) -> bool:
        if URL_PATTERN.search(previous) or URL_PATTERN.search(current):
            return False
        if previous.endswith((".", "!", "?", ":")):
            return False
        if re.match(r"^(order|total|status|item|tracking)\b", current, re.IGNORECASE):
            return False
        return True

    @staticmethod
    def _looks_like_hidden_preheader(line: str) -> bool:
        lowered = line.lower().strip()
        if not lowered:
            return False
        if len(lowered) > 120:
            return False
        return (
            "view in browser" in lowered
            or "add us to your address book" in lowered
            or sum(ch in {"_", "-", ".", "*"} for ch in lowered) > max(6, len(lowered) // 2)
        )

    @staticmethod
    def _low_value_line(line: str) -> bool:
        if len(line) <= 1:
            return True
        alnum_count = sum(ch.isalnum() for ch in line)
        return alnum_count == 0

    @staticmethod
    def _classify_link(*, label: str | None, url: str) -> str:
        text = f"{label or ''} {url}".strip()
        for link_type, pattern in IMPORTANT_LINK_PATTERNS.items():
            if pattern.search(text):
                return link_type
        return "other"

    def _build_link(self, *, url: str, label: str | None, source: str, raw_url: str | None = None) -> GmailPhase2Link:
        normalized_url, diagnostics, is_valid = self._normalize_url(url)
        if raw_url and raw_url != url:
            diagnostics = ["url_sanitized:repaired_from_context", *diagnostics]
        return GmailPhase2Link(
            label=label,
            url=normalized_url or url,
            raw_url=raw_url or url,
            normalized_url=normalized_url,
            link_type=self._classify_link(label=label, url=normalized_url or url),  # type: ignore[arg-type]
            source=source,  # type: ignore[arg-type]
            is_tracking=any(pattern.search(normalized_url or url) for pattern in TRACKING_HOST_PATTERNS),
            is_valid=is_valid,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _normalize_url(url: str) -> tuple[str | None, list[str], bool]:
        diagnostics: list[str] = []
        original = url.strip()
        had_control_chars = any(ord(ch) < 32 or ch == "\x7f" for ch in original)
        cleaned = "".join(ch for ch in original if ch >= " " and ch != "\x7f").strip()
        if had_control_chars and cleaned != original:
            diagnostics.append("url_sanitized:control_characters_removed")
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = cleaned.replace("&amp;", "&")
        cleaned = cleaned.replace("C>", "C=")
        cleaned = re.sub(r"(orderID)(?=\d)", r"\1=", cleaned)
        cleaned = re.sub(r"(nodeId)(?=\d)", r"\1=", cleaned)
        parsed = urlparse(cleaned)
        if not parsed.scheme or not parsed.netloc:
            diagnostics.append("invalid_url:missing_scheme_or_host")
            return cleaned or None, diagnostics, False
        if "amazon.com" in parsed.netloc:
            params = parse_qs(parsed.query)
            redirect = params.get("U") or params.get("u")
            if redirect:
                target = unquote(redirect[0])
                redirected = urlparse(target)
                if redirected.scheme and redirected.netloc:
                    diagnostics.append("normalized_url:used_embedded_redirect_target")
                    cleaned = target
                    parsed = redirected
        else:
            cleaned = unquote(cleaned, errors="ignore")
            parsed = urlparse(cleaned)
        if any(ord(ch) < 32 for ch in cleaned):
            diagnostics.append("invalid_url:control_characters_present")
            cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32)
            return cleaned, diagnostics, False
        return cleaned, diagnostics, True

    def _prioritize_links(self, links: list[GmailPhase2Link]) -> list[GmailPhase2Link]:
        normalized_links = [
            self._build_link(
                url=link.normalized_url or link.url,
                raw_url=link.raw_url,
                label=link.label,
                source=link.source,
            )
            for link in links
        ]

        def rank(link: GmailPhase2Link) -> tuple[int, int]:
            priority = {
                "order_action": 5,
                "tracking_action": 4,
                "document_action": 3,
                "account": 2,
                "other": 1,
            }.get(link.link_type, 0)
            if not link.is_valid:
                priority -= 2
            if link.is_tracking:
                priority -= 1
            return priority, len(link.label or "")

        ordered = sorted(normalized_links, key=rank, reverse=True)
        return [link for link in ordered if rank(link)[0] > 0][:6]

    def _split_into_blocks(self, text: str) -> list[str]:
        if not text.strip():
            return []
        blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
        if blocks:
            return blocks
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return ["\n".join(lines)] if lines else []

    def _score_transactional_block(self, block: str) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        lowered = block.lower()
        for pattern in TRANSACTIONAL_ANCHOR_PATTERNS:
            if pattern.search(lowered):
                score += 2
                reasons.append(f"transactional_anchor:{pattern.pattern}")
        has_order_identifier = self._has_order_identifier(block)
        has_status = self._has_status(block)
        has_greeting = self._has_greeting(block)
        has_item = self._has_item_line(block)
        has_quantity = self._has_quantity(block)
        has_total = self._has_total(block)
        has_price = self._has_price(block)
        if has_order_identifier:
            score += 8
            reasons.append("order_identifier")
        if has_status:
            score += 6
            reasons.append("status_anchor")
        if has_greeting:
            score += 4
            reasons.append("greeting_anchor")
        if has_item:
            score += 4
            reasons.append("item_anchor")
        if has_quantity:
            score += 2
            reasons.append("quantity_anchor")
        if has_total:
            score += 2
            reasons.append("total_anchor")
        if has_price:
            score += 1
        if has_order_identifier and (has_status or has_greeting):
            score += 6
            reasons.append("completeness:header_context")
        if has_order_identifier and (has_item or has_total):
            score += 5
            reasons.append("completeness:order_plus_item_or_total")
        if has_status and (has_item or has_total):
            score += 3
            reasons.append("completeness:status_plus_item_or_total")
        if not has_order_identifier and (has_quantity or has_total or has_price):
            score -= 3
            reasons.append("penalty:price_without_order_identifier")
        if not (has_order_identifier or has_status or has_greeting) and has_item and has_total:
            score -= 2
            reasons.append("penalty:item_total_without_header")
        if re.search(r"%\s*off", lowered):
            score -= 3
            reasons.append("promo_marker:% off")
        for pattern in PROMO_MARKER_PATTERNS:
            if pattern.search(lowered):
                score -= 3
                reasons.append(f"promo_marker:{pattern.pattern}")
        return score, reasons

    def _expand_supporting_blocks(self, blocks: list[str], index: int) -> tuple[str, list[str], list[str]]:
        included = {index}
        diagnostics = [f"merged block {index}:seed"]
        applied_rules = ["transactional_targeting:seed_block_selected"]
        baseline_block = blocks[index].strip()
        baseline_features = self._block_features(baseline_block)
        for direction in (-1, 1):
            steps = 0
            skipped_neutral = 0
            cursor = index + direction
            current_features = dict(baseline_features)
            while 0 <= cursor < len(blocks) and steps < 4:
                steps += 1
                block = blocks[cursor].strip()
                if not block:
                    cursor += direction
                    continue
                if self._is_promo_block(block):
                    diagnostics.append(f"rejected block {cursor}:promo_guard")
                    applied_rules.append("transactional_targeting:promo_merge_rejected")
                    break
                score, reasons = self._score_transactional_block(block)
                candidate_features = self._block_features(block)
                if self._should_merge_block(current_features, candidate_features, score):
                    included.add(cursor)
                    diagnostics.append(
                        f"merged block {cursor}:complementary anchors={','.join(self._feature_names(candidate_features)) or 'none'} score={score}"
                    )
                    applied_rules.append("transactional_targeting:merged_adjacent_block")
                    current_features = self._merge_feature_maps(current_features, candidate_features)
                    cursor += direction
                    continue
                if score <= 0 and skipped_neutral < 1 and not self._is_promo_block(block):
                    skipped_neutral += 1
                    diagnostics.append(f"skipped block {cursor}:neutral_bridge")
                    cursor += direction
                    continue
                diagnostics.append(f"rejected block {cursor}:score={score} reasons={';'.join(reasons[:4]) or 'none'}")
                break
        if not current_features.get("greeting"):
            for distance in range(1, 7):
                for cursor in (index - distance, index + distance):
                    if cursor < 0 or cursor >= len(blocks) or cursor in included:
                        continue
                    block = blocks[cursor].strip()
                    if not block or self._is_promo_block(block) or not self._has_greeting(block):
                        continue
                    included.add(cursor)
                    diagnostics.append(f"merged block {cursor}:greeting_context_recovery")
                    applied_rules.append("transactional_targeting:merged_greeting_context")
                    current_features = self._merge_feature_maps(current_features, self._block_features(block))
                    break
                if current_features.get("greeting"):
                    break
        selected = [blocks[position].strip() for position in sorted(included) if blocks[position].strip()]
        return "\n\n".join(selected).strip(), diagnostics, applied_rules

    @staticmethod
    def _is_supporting_block(block: str) -> bool:
        lowered = block.lower()
        return bool(
            re.search(r"\b(order|quantity|total|arriving|delivered|shipped)\b", lowered)
            or re.search(r"\b\d{3}-\d{7}-\d{7}\b", lowered)
            or lowered.startswith("http")
        )

    def _transactional_completeness(self, normalized_lines: list[str]) -> tuple[str, list[str]]:
        text = "\n".join(normalized_lines)
        checks = {
            "order_identifier": self._has_order_identifier(text),
            "status": self._has_status(text) or self._has_greeting(text),
            "item_line": self._has_item_line(text),
            "quantity": self._has_quantity(text),
            "total": self._has_total(text),
        }
        present = sum(1 for ok in checks.values() if ok)
        diagnostics = [f"transactional_completeness:{name}=missing" for name, ok in checks.items() if not ok]
        if not checks["order_identifier"] and not checks["status"]:
            diagnostics.append("transactional_downgrade:missing_order_identifier_and_status")
            return "failed", diagnostics
        if not checks["order_identifier"] or not checks["status"]:
            diagnostics.append("transactional_downgrade:missing_critical_order_anchor")
            return "partial", diagnostics
        if present >= 4:
            return "success", diagnostics
        if present >= 1:
            return "partial", diagnostics
        return "failed", diagnostics

    @staticmethod
    def _is_likely_transactional_email(text: str) -> bool:
        lowered = text.lower()
        return any(pattern.search(lowered) for pattern in TRANSACTIONAL_ANCHOR_PATTERNS)

    @staticmethod
    def _merge_feature_maps(left: dict[str, bool], right: dict[str, bool]) -> dict[str, bool]:
        return {key: left.get(key, False) or right.get(key, False) for key in set(left) | set(right)}

    def _block_features(self, block: str) -> dict[str, bool]:
        return {
            "order_identifier": self._has_order_identifier(block),
            "status": self._has_status(block),
            "greeting": self._has_greeting(block),
            "item": self._has_item_line(block),
            "quantity": self._has_quantity(block),
            "total": self._has_total(block),
            "price": self._has_price(block),
            "action_link": self._has_action_link(block),
        }

    @staticmethod
    def _feature_names(features: dict[str, bool]) -> list[str]:
        return [name for name, present in features.items() if present]

    def _should_merge_block(self, current: dict[str, bool], candidate: dict[str, bool], score: int) -> bool:
        if score <= 0 and not candidate["order_identifier"] and not candidate["status"]:
            return False
        if candidate["price"] and not any(candidate[key] for key in ("order_identifier", "status", "greeting", "item", "quantity", "total")):
            return False
        complementary = (
            (candidate["order_identifier"] and not current["order_identifier"])
            or (candidate["status"] and not current["status"])
            or (candidate["greeting"] and not current["greeting"])
            or (candidate["item"] and not current["item"])
            or (candidate["quantity"] and not current["quantity"])
            or (candidate["total"] and not current["total"])
            or (candidate["action_link"] and not current["action_link"])
        )
        supportive = candidate["item"] or candidate["quantity"] or candidate["total"] or candidate["price"] or candidate["action_link"]
        current_has_header = current["order_identifier"] or current["status"] or current["greeting"]
        candidate_has_header = candidate["order_identifier"] or candidate["status"] or candidate["greeting"]
        header_completion = candidate_has_header and (current["order_identifier"] or current["status"] or current["greeting"])
        return complementary and (
            (current_has_header and supportive)
            or (candidate_has_header and (current["item"] or current["total"]))
            or header_completion
        )

    def _is_promo_block(self, block: str) -> bool:
        lowered = block.lower()
        promo_hits = sum(1 for pattern in PROMO_MARKER_PATTERNS if pattern.search(lowered))
        if promo_hits:
            return True
        if len(re.findall(r"-\d+%\s+\$\d", lowered)) >= 1:
            return True
        if "deal" in lowered and not self._has_order_identifier(block):
            return True
        if "recommended" in lowered or "buy again" in lowered:
            return True
        return False

    def _coalesce_semantic_lines(self, lines: list[str]) -> list[str]:
        combined: list[str] = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if line == "":
                combined.append(line)
                index += 1
                continue
            next_line = lines[index + 1] if index + 1 < len(lines) else None
            if line.lower() in {"order #", "order number:", "order number", "reference number:", "reference #"} and next_line and self._has_order_identifier(next_line):
                label = line if line.endswith(":") else f"{line}:"
                combined.append(f"{label} {next_line}")
                index += 2
                continue
            combined.append(line)
            index += 1
        priority_groups = {"greeting": [], "status": [], "order_identifier": [], "other": []}
        for line in combined:
            if line == "":
                continue
            if self._has_greeting(line):
                priority_groups["greeting"].append(line)
            elif self._has_status(line):
                priority_groups["status"].append(line)
            elif self._has_order_identifier(line):
                priority_groups["order_identifier"].append(line)
            else:
                priority_groups["other"].append(line)
        ordered = priority_groups["greeting"] + priority_groups["status"] + priority_groups["order_identifier"] + priority_groups["other"]
        deduped: list[str] = []
        seen: set[str] = set()
        for line in ordered:
            if line in seen:
                continue
            seen.add(line)
            deduped.append(line)
        return deduped

    @staticmethod
    def _has_order_identifier(text: str) -> bool:
        visible_text = URL_PATTERN.sub(" ", text)
        return bool(ORDER_ID_PATTERN.search(visible_text) or BARE_ORDER_ID_PATTERN.search(visible_text))

    @staticmethod
    def _first_order_identifier(text: str) -> str | None:
        visible_text = URL_PATTERN.sub(" ", text)
        match = BARE_ORDER_ID_PATTERN.search(visible_text)
        if match:
            return match.group(0)
        match = ORDER_ID_PATTERN.search(visible_text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _has_status(text: str) -> bool:
        return bool(STATUS_PATTERN.search(text))

    @staticmethod
    def _has_greeting(text: str) -> bool:
        return bool(GREETING_PATTERN.search(text))

    @staticmethod
    def _has_item_line(text: str) -> bool:
        return bool(ITEM_PATTERN.search(text))

    @staticmethod
    def _has_quantity(text: str) -> bool:
        return bool(QUANTITY_PATTERN.search(text))

    @staticmethod
    def _has_total(text: str) -> bool:
        return bool(TOTAL_PATTERN.search(text))

    @staticmethod
    def _has_price(text: str) -> bool:
        return bool(PRICE_PATTERN.search(text))

    @staticmethod
    def _has_action_link(text: str) -> bool:
        return bool(ACTION_LINK_PATTERN.search(text))

    @staticmethod
    def _repair_order_action_url(url: str, context_order_id: str | None) -> str:
        if not context_order_id or "orderID" not in url:
            return url
        prefix, _, remainder = url.partition("orderID")
        if not remainder:
            return url
        suffix = ""
        if "&" in remainder:
            suffix = "&" + remainder.split("&", 1)[1]
        return f"{prefix}orderID={context_order_id}{suffix}"

    @staticmethod
    def _diagnostics(items: list[str]) -> list[GmailPhase1DiagnosticItem]:
        diagnostics: list[GmailPhase1DiagnosticItem] = []
        for item in items:
            code = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_") or "diagnostic"
            diagnostics.append(GmailPhase1DiagnosticItem(code=code, detail=item))
        return diagnostics

    @staticmethod
    def _reduction_ratio(input_chars: int, output_chars: int) -> float:
        if input_chars <= 0:
            return 0.0
        return max(0.0, min(1.0, 1 - (output_chars / input_chars)))

    @staticmethod
    def _phase1_reference(phase1: GmailPhase1NormalizedEmail) -> GmailPhase1Reference:
        return GmailPhase1Reference(
            schema_version=phase1.schema_version,
            provider=phase1.provider,
            message_id=phase1.message_id,
            thread_id=phase1.thread_id,
            provider_message_id=phase1.provider_message_id,
            provider_thread_id=phase1.provider_thread_id,
            rfc_message_id=phase1.rfc_message_id,
            subject=phase1.subject,
            sender_name=phase1.sender_name,
            sender_email=phase1.sender_email,
            sender_domain=phase1.sender_domain,
            received_at=phase1.received_at,
            selected_body_type=phase1.selected_body_type,
            selected_body_source=phase1.selected_body_source,
            selected_body_selection_path=phase1.selected_body_selection_path,
            handoff_ready=phase1.handoff_ready,
            fetch_status=phase1.fetch_status,
            mime_parse_status=phase1.mime_parse_status,
            validation_status=phase1.validation_status,
        )
