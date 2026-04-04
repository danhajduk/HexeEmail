from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from providers.gmail.models import (
    GmailPhase1DiagnosticItem,
    GmailPhase2Link,
    GmailPhase3DetectedEmail,
    GmailPhase4ExtractedEmail,
    GmailPhase4ExtractedField,
    GmailPhase4NormalizationMetadata,
    GmailPhase4TemplateCandidate,
    GmailPhase4WorkingEmail,
)
from providers.gmail.order_template_registry import GmailOrderTemplateRegistry, TEMPLATE_SCHEMA_VERSION


EXTRACTOR_VERSION = "order-phase4-template-extractor.v1"


class GmailOrderPhase4Extractor:
    def __init__(self, registry: GmailOrderTemplateRegistry | None = None) -> None:
        self.registry = registry or GmailOrderTemplateRegistry()

    def extract(self, phase3: GmailPhase3DetectedEmail) -> GmailPhase4ExtractedEmail:
        working, intake_error = self.build_working_object(phase3)
        if working is None:
            diagnostics = [intake_error or "phase3 payload is not ready for template extraction"]
            stage_statuses = {
                "intake": "failed",
                "template_lookup": "failed",
                "template_execution": "failed",
                "field_validation": "failed",
                "confidence_scoring": "failed",
            }
            stage_diagnostics = {name: self._diagnostics(diagnostics) for name in stage_statuses}
            return GmailPhase4ExtractedEmail(
                phase3_reference=phase3,
                message_id=phase3.message_id,
                thread_id=phase3.thread_id,
                provider_message_id=phase3.provider_message_id,
                provider_thread_id=phase3.provider_thread_id,
                rfc_message_id=phase3.rfc_message_id,
                subject=phase3.subject,
                sender_name=phase3.sender_name,
                sender_email=phase3.sender_email,
                sender_domain=phase3.sender_domain,
                sender_identity=phase3.sender_identity,
                vendor_identity=phase3.vendor_identity,
                profile_id=phase3.profile_id,
                profile_family=phase3.profile_family,
                profile_subtype=phase3.profile_subtype,
                profile_confidence=phase3.profile_confidence,
                extraction_status="failed",
                field_diagnostics=diagnostics,
                template_diagnostics=diagnostics,
                ai_template_hook=self.build_ai_template_hook(phase3),
                stage_statuses=stage_statuses,
                stage_diagnostics=stage_diagnostics,
                normalization_metadata=GmailPhase4NormalizationMetadata(
                    extractor_version=EXTRACTOR_VERSION,
                    template_schema_version=TEMPLATE_SCHEMA_VERSION,
                    normalized_at=datetime.now().astimezone(),
                ),
            )

        template, fallback_templates, lookup_diagnostics = self.lookup_template(working)
        stage_statuses = {"intake": "success"}
        stage_diagnostics = {"intake": working.stage_diagnostics.get("intake", self._diagnostics([]))}
        stage_statuses["template_lookup"] = "success" if template else "partial"
        stage_diagnostics["template_lookup"] = self._diagnostics(lookup_diagnostics)

        if template is None:
            diagnostics = lookup_diagnostics + ["template_execution:skipped_no_template"]
            return GmailPhase4ExtractedEmail(
                phase3_reference=phase3,
                message_id=working.message_id,
                thread_id=working.thread_id,
                provider_message_id=working.provider_message_id,
                provider_thread_id=working.provider_thread_id,
                rfc_message_id=working.rfc_message_id,
                subject=working.subject,
                sender_name=working.sender_name,
                sender_email=working.sender_email,
                sender_domain=working.sender_domain,
                sender_identity=working.sender_identity,
                vendor_identity=working.vendor_identity,
                profile_id=working.profile_id,
                profile_family=working.profile_family,
                profile_subtype=working.profile_subtype,
                profile_confidence=working.profile_confidence,
                extraction_status="unresolved",
                template_diagnostics=diagnostics,
                fallback_templates=fallback_templates,
                ai_template_hook=self.build_ai_template_hook(phase3),
                stage_statuses={
                    **stage_statuses,
                    "template_execution": "partial",
                    "field_validation": "partial",
                    "confidence_scoring": "partial",
                },
                stage_diagnostics={
                    **stage_diagnostics,
                    "template_execution": self._diagnostics(["template_execution:skipped_no_template"]),
                    "field_validation": self._diagnostics([]),
                    "confidence_scoring": self._diagnostics(["confidence:unresolved_no_template"]),
                },
                normalization_metadata=GmailPhase4NormalizationMetadata(
                    extractor_version=EXTRACTOR_VERSION,
                    template_schema_version=TEMPLATE_SCHEMA_VERSION,
                    normalized_at=datetime.now().astimezone(),
                ),
            )

        extracted_fields, field_diagnostics, template_execution_diagnostics = self.run_template(working, template)
        stage_statuses["template_execution"] = "success" if extracted_fields else "partial"
        stage_diagnostics["template_execution"] = self._diagnostics(template_execution_diagnostics)

        extracted_fields, validation_diagnostics = self.validate_fields(
            extracted_fields,
            required_fields=template.get("required_fields", []),
        )
        stage_statuses["field_validation"] = "success" if not any("missing_required" in item for item in validation_diagnostics) else "partial"
        stage_diagnostics["field_validation"] = self._diagnostics(validation_diagnostics)

        confidence, confidence_level, confidence_diagnostics, extraction_status = self.score_extraction_confidence(
            extracted_fields,
            required_fields=template.get("required_fields", []),
        )
        stage_statuses["confidence_scoring"] = extraction_status if extraction_status in {"success", "partial"} else "failed"
        stage_diagnostics["confidence_scoring"] = self._diagnostics(confidence_diagnostics)

        template_diagnostics = lookup_diagnostics + template_execution_diagnostics + validation_diagnostics + confidence_diagnostics
        return GmailPhase4ExtractedEmail(
            phase3_reference=phase3,
            message_id=working.message_id,
            thread_id=working.thread_id,
            provider_message_id=working.provider_message_id,
            provider_thread_id=working.provider_thread_id,
            rfc_message_id=working.rfc_message_id,
            subject=working.subject,
            sender_name=working.sender_name,
            sender_email=working.sender_email,
            sender_domain=working.sender_domain,
            sender_identity=working.sender_identity,
            vendor_identity=working.vendor_identity,
            profile_id=working.profile_id,
            profile_family=working.profile_family,
            profile_subtype=working.profile_subtype,
            profile_confidence=working.profile_confidence,
            template_id=str(template.get("template_id")),
            template_version=str(template.get("template_version")),
            extraction_status=extraction_status,  # type: ignore[arg-type]
            extraction_confidence=confidence,
            extraction_confidence_level=confidence_level,  # type: ignore[arg-type]
            extracted_fields=extracted_fields,
            field_diagnostics=field_diagnostics + validation_diagnostics,
            template_diagnostics=template_diagnostics,
            fallback_templates=fallback_templates,
            ai_template_hook=self.build_ai_template_hook(phase3),
            stage_statuses=stage_statuses,
            stage_diagnostics=stage_diagnostics,
            normalization_metadata=GmailPhase4NormalizationMetadata(
                extractor_version=EXTRACTOR_VERSION,
                template_schema_version=TEMPLATE_SCHEMA_VERSION,
                normalized_at=datetime.now().astimezone(),
            ),
        )

    def build_working_object(self, phase3: GmailPhase3DetectedEmail) -> tuple[GmailPhase4WorkingEmail | None, str | None]:
        if not phase3.profile_id:
            return None, "phase3 profile_id is missing"
        phase2 = phase3.phase2_reference
        if not phase2.scrubbed_text.strip():
            return None, "phase2 scrubbed_text is empty"
        diagnostics = [f"usable_phase3_profile:{phase3.profile_id}"]
        return (
            GmailPhase4WorkingEmail(
                phase3_reference=phase3,
                message_id=phase3.message_id,
                thread_id=phase3.thread_id,
                provider_message_id=phase3.provider_message_id,
                provider_thread_id=phase3.provider_thread_id,
                rfc_message_id=phase3.rfc_message_id,
                subject=phase3.subject,
                sender_name=phase3.sender_name,
                sender_email=phase3.sender_email,
                sender_domain=phase3.sender_domain,
                sender_identity=phase3.sender_identity,
                vendor_identity=phase3.vendor_identity,
                profile_id=phase3.profile_id,
                profile_family=phase3.profile_family,
                profile_subtype=phase3.profile_subtype,
                profile_confidence=phase3.profile_confidence,
                scrubbed_text=phase2.scrubbed_text,
                normalized_lines=list(phase2.normalized_lines),
                extracted_links=list(phase2.extracted_links),
                stage_statuses={"intake": "success"},
                stage_diagnostics={"intake": self._diagnostics(diagnostics)},
            ),
            None,
        )

    def lookup_template(
        self,
        working: GmailPhase4WorkingEmail,
    ) -> tuple[dict[str, object] | None, list[GmailPhase4TemplateCandidate], list[str]]:
        template, fallbacks, diagnostics = self.registry.lookup(
            profile_id=working.profile_id,
            vendor_identity=working.vendor_identity,
        )
        fallback_models = [
            GmailPhase4TemplateCandidate(
                template_id=str(item.get("template_id")),
                template_version=str(item.get("template_version")),
                profile_id=str(item.get("profile_id")),
            )
            for item in fallbacks
        ]
        if template:
            diagnostics.extend(self.registry.validate_template(template))
        return template, fallback_models, diagnostics

    def run_template(
        self,
        working: GmailPhase4WorkingEmail,
        template: dict[str, object],
    ) -> tuple[dict[str, GmailPhase4ExtractedField], list[str], list[str]]:
        extracted_fields: dict[str, GmailPhase4ExtractedField] = {}
        field_diagnostics: list[str] = []
        template_diagnostics: list[str] = []
        rules = template.get("extract", {})
        if not isinstance(rules, dict):
            return {}, [], ["template_execution:extract_rules_missing"]
        for field_name, rule in rules.items():
            if not isinstance(rule, dict):
                continue
            value, diagnostics = self._execute_rule(working, rule)
            transforms = [str(item) for item in rule.get("transforms", []) or []]
            normalized_value, transform_diagnostics = self._apply_transforms(value, transforms)
            extracted_fields[field_name] = GmailPhase4ExtractedField(
                field_name=field_name,
                value=normalized_value,
                source_method=str(rule.get("method")),
                source_rule=str(rule.get("name") or field_name),
                transforms_applied=transforms,
                diagnostics=diagnostics + transform_diagnostics,
                is_valid=True,
            )
            field_diagnostics.extend(f"{field_name}:{item}" for item in diagnostics + transform_diagnostics)
            template_diagnostics.append(f"template_execution:field:{field_name}")
        return extracted_fields, field_diagnostics, template_diagnostics

    def validate_fields(
        self,
        extracted_fields: dict[str, GmailPhase4ExtractedField],
        *,
        required_fields: object,
    ) -> tuple[dict[str, GmailPhase4ExtractedField], list[str]]:
        required = [str(item) for item in required_fields or []]
        diagnostics: list[str] = []
        updated = dict(extracted_fields)
        for field_name in required:
            field = updated.get(field_name)
            if field is None or self._is_missing_value(field.value):
                diagnostics.append(f"missing_required:{field_name}")
                updated[field_name] = GmailPhase4ExtractedField(
                    field_name=field_name,
                    value=None,
                    is_valid=False,
                    is_required=True,
                    diagnostics=["required_field_missing"],
                )
                continue
            updated[field_name] = field.model_copy(update={"is_required": True})
        for field_name, field in list(updated.items()):
            value = field.value
            field_diags = list(field.diagnostics)
            is_valid = field.is_valid
            if field_name.endswith("_url") and isinstance(value, str):
                parsed = urlparse(value)
                if not parsed.scheme or not parsed.netloc:
                    is_valid = False
                    field_diags.append("invalid_url_shape")
                    diagnostics.append(f"invalid_field:{field_name}")
            if field_name in {"order_number", "tracking_number"} and isinstance(value, str):
                if len(re.sub(r"[^A-Z0-9-]", "", value.upper())) < 6:
                    is_valid = False
                    field_diags.append("value_too_short")
                    diagnostics.append(f"invalid_field:{field_name}")
            updated[field_name] = field.model_copy(update={"is_valid": is_valid, "diagnostics": field_diags})
        return updated, diagnostics

    def score_extraction_confidence(
        self,
        extracted_fields: dict[str, GmailPhase4ExtractedField],
        *,
        required_fields: object,
    ) -> tuple[float, str, list[str], str]:
        required = [str(item) for item in required_fields or []]
        diagnostics: list[str] = []
        present_required = sum(
            1 for name in required if name in extracted_fields and not self._is_missing_value(extracted_fields[name].value)
        )
        total_required = len(required)
        valid_fields = sum(1 for field in extracted_fields.values() if field.is_valid and not self._is_missing_value(field.value))
        total_fields = max(1, len(extracted_fields))
        confidence = 0.0
        if total_required:
            confidence += 0.6 * (present_required / total_required)
        confidence += 0.4 * (valid_fields / total_fields)
        confidence = round(min(1.0, confidence), 2)
        if total_required and present_required < total_required:
            diagnostics.append("confidence_downgrade:missing_required_fields")
        if valid_fields < total_fields:
            diagnostics.append("confidence_downgrade:invalid_optional_fields")
        if confidence >= 0.85:
            return confidence, "high", diagnostics, "success"
        if confidence >= 0.5:
            return confidence, "medium", diagnostics, "partial"
        return confidence, "low", diagnostics, "partial"

    def build_ai_template_hook(self, phase3: GmailPhase3DetectedEmail) -> dict[str, object]:
        phase2 = phase3.phase2_reference
        return {
            "sender_identity": phase3.sender_identity,
            "vendor_identity": phase3.vendor_identity,
            "profile_id": phase3.profile_id,
            "profile_family": phase3.profile_family,
            "profile_subtype": phase3.profile_subtype,
            "subject": phase3.subject,
            "scrubbed_text": phase2.scrubbed_text,
            "normalized_lines": list(phase2.normalized_lines),
            "extracted_links": [
                link.model_dump() if hasattr(link, "model_dump") else dict(link)
                for link in phase2.extracted_links
            ],
            "expected_output_schema": {
                "template_id": "candidate_template_id",
                "profile_id": phase3.profile_id,
                "template_version": "v1",
                "enabled": True,
                "match": {},
                "extract": {},
                "required_fields": [],
                "confidence_rules": {},
                "post_process": {},
            },
        }

    def _execute_rule(
        self,
        working: GmailPhase4WorkingEmail,
        rule: dict[str, object],
    ) -> tuple[object | None, list[str]]:
        method = str(rule.get("method") or "")
        diagnostics: list[str] = []
        source_text = working.scrubbed_text
        lines = list(working.normalized_lines)
        if method == "regex":
            pattern = re.compile(str(rule.get("pattern") or ""), re.IGNORECASE)
            match = pattern.search(source_text)
            return (match.group(1) if match and match.groups() else (match.group(0) if match else None), diagnostics)
        if method == "first_match":
            pattern = re.compile(str(rule.get("pattern") or ""), re.IGNORECASE)
            match = pattern.search(source_text)
            return (match.group(0) if match else None, diagnostics)
        if method == "all_matches":
            pattern = re.compile(str(rule.get("pattern") or ""), re.IGNORECASE)
            return pattern.findall(source_text), diagnostics
        if method == "line_contains":
            needle = str(rule.get("value") or "").lower()
            for line in lines:
                if needle in line.lower():
                    return line, diagnostics
            return None, diagnostics
        if method == "line_after":
            marker = str(rule.get("marker") or "").lower()
            for index, line in enumerate(lines[:-1]):
                if marker in line.lower():
                    return lines[index + 1], diagnostics
            return None, diagnostics
        if method == "between_markers":
            start = str(rule.get("start") or "")
            end = str(rule.get("end") or "")
            if start in source_text and end in source_text.split(start, 1)[1]:
                return source_text.split(start, 1)[1].split(end, 1)[0].strip(), diagnostics
            return None, diagnostics
        if method == "link_by_label":
            needle = str(rule.get("label") or "").lower()
            link = self._find_link_by_label(working.extracted_links, needle)
            return (link.normalized_url or link.url) if link else None, diagnostics
        if method == "link_by_type":
            link_type = str(rule.get("link_type") or "")
            for link in working.extracted_links:
                if link.link_type == link_type:
                    return link.normalized_url or link.url, diagnostics
            return None, diagnostics
        diagnostics.append(f"unsupported_method:{method}")
        return None, diagnostics

    @staticmethod
    def _find_link_by_label(links: list[GmailPhase2Link], needle: str) -> GmailPhase2Link | None:
        for link in links:
            if link.label and needle in link.label.lower():
                return link
        return None

    @staticmethod
    def _is_missing_value(value: object | None) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value == ""
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) == 0
        return False

    def _apply_transforms(self, value: object | None, transforms: list[str]) -> tuple[object | None, list[str]]:
        if value is None:
            return None, []
        diagnostics: list[str] = []
        result = value
        for transform in transforms:
            if isinstance(result, str):
                if transform == "trim":
                    result = result.strip()
                elif transform == "collapse_spaces":
                    result = re.sub(r"\s+", " ", result).strip()
                elif transform == "normalize_currency":
                    result = re.sub(r"\s*usd\b", " USD", result, flags=re.IGNORECASE).replace("$ ", "$")
                elif transform == "normalize_order_number":
                    result = re.sub(r"[^A-Z0-9-]", "", result.upper())
                elif transform == "normalize_phone_number":
                    digits = re.sub(r"\D", "", result)
                    result = digits
                elif transform == "normalize_url":
                    result = result.strip()
                diagnostics.append(f"transform:{transform}")
        return result, diagnostics

    @staticmethod
    def _diagnostics(items: list[str]) -> list[GmailPhase1DiagnosticItem]:
        diagnostics: list[GmailPhase1DiagnosticItem] = []
        for item in items:
            code = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_") or "diagnostic"
            diagnostics.append(GmailPhase1DiagnosticItem(code=code, detail=item))
        return diagnostics
