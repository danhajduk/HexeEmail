from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from providers.gmail.models import (
    GmailPhase1DiagnosticItem,
    GmailPhase2ScrubbedEmail,
    GmailPhase3DetectedEmail,
    GmailPhase3NormalizationMetadata,
    GmailPhase3ProfileCandidate,
    GmailPhase3WorkingEmail,
)


PROFILE_DETECTOR_VERSION = "order-phase3-profile-detector.v1"
ORDER_ID_PATTERN = re.compile(r"\b\d{3}-\d{7}-\d{7}\b")


class SharedProfileDetectorEngine:
    def __init__(
        self,
        *,
        taxonomy: dict[str, dict[str, str | None]],
        taxonomy_version: str,
        known_vendor_identities: dict[str, str],
        rules: dict[str, object],
    ) -> None:
        self.taxonomy = taxonomy
        self.taxonomy_version = taxonomy_version
        self.known_vendor_identities = known_vendor_identities
        self.rules = rules

    def detect(self, phase2: GmailPhase2ScrubbedEmail) -> GmailPhase3DetectedEmail:
        working, intake_error = self.build_working_object(phase2)
        if working is None:
            diagnostics = [intake_error or "phase2 payload is not ready for profile detection"]
            stage_statuses = {
                "intake": "failed",
                "candidate_generation": "failed",
                "candidate_scoring": "failed",
                "profile_resolution": "failed",
            }
            stage_diagnostics = {name: self._diagnostics(diagnostics) for name in stage_statuses}
            return GmailPhase3DetectedEmail(
                phase2_reference=phase2,
                message_id=phase2.message_id,
                thread_id=phase2.thread_id,
                provider_message_id=phase2.provider_message_id,
                provider_thread_id=phase2.provider_thread_id,
                rfc_message_id=phase2.rfc_message_id,
                subject=phase2.subject,
                sender_name=phase2.sender_name,
                sender_email=phase2.sender_email,
                sender_domain=phase2.sender_domain,
                sender_identity=self._sender_identity(phase2.sender_name, phase2.sender_domain),
                vendor_identity=self._vendor_identity(phase2.sender_domain),
                profile_status="failed",
                profile_diagnostics=diagnostics,
                stage_statuses=stage_statuses,
                stage_diagnostics=stage_diagnostics,
                normalization_metadata=GmailPhase3NormalizationMetadata(
                    profile_detector_version=PROFILE_DETECTOR_VERSION,
                    taxonomy_version=self.taxonomy_version,
                    normalized_at=datetime.now().astimezone(),
                ),
            )

        candidates, generation_diagnostics = self.generate_candidates(working)
        candidate_status = "success" if candidates else "partial"
        ranked_candidates, scoring_diagnostics = self.score_candidates(working, candidates)
        primary, fallbacks, confidence, confidence_level, resolution_diagnostics, profile_status = self.resolve_profile(
            working,
            ranked_candidates,
        )
        stage_statuses = {
            "intake": "success",
            "candidate_generation": candidate_status,
            "candidate_scoring": "success" if ranked_candidates else "partial",
            "profile_resolution": profile_status,
        }
        stage_diagnostics = {
            "intake": working.stage_diagnostics.get("intake", self._diagnostics([])),
            "candidate_generation": self._diagnostics(generation_diagnostics),
            "candidate_scoring": self._diagnostics(scoring_diagnostics),
            "profile_resolution": self._diagnostics(resolution_diagnostics),
        }
        diagnostics = generation_diagnostics + scoring_diagnostics + resolution_diagnostics
        return GmailPhase3DetectedEmail(
            phase2_reference=phase2,
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
            profile_id=primary.profile_id if primary else None,
            profile_family=primary.profile_family if primary else None,
            profile_subtype=primary.profile_subtype if primary else None,
            profile_confidence=confidence,
            profile_confidence_level=confidence_level,
            profile_status=profile_status,
            candidate_profiles=ranked_candidates,
            fallback_profiles=fallbacks,
            profile_diagnostics=list(dict.fromkeys(diagnostics)),
            stage_statuses=stage_statuses,
            stage_diagnostics=stage_diagnostics,
            normalization_metadata=GmailPhase3NormalizationMetadata(
                profile_detector_version=PROFILE_DETECTOR_VERSION,
                taxonomy_version=self.taxonomy_version,
                normalized_at=datetime.now().astimezone(),
            ),
        )

    def build_working_object(self, phase2: GmailPhase2ScrubbedEmail) -> tuple[GmailPhase3WorkingEmail | None, str | None]:
        if phase2.scrub_status == "failed":
            return None, "phase2 scrub_status is failed"
        if not phase2.scrubbed_text.strip():
            return None, "phase2 scrubbed_text is empty"
        diagnostics = [f"usable_phase2_scrub_status:{phase2.scrub_status}"]
        return (
            GmailPhase3WorkingEmail(
                phase2_reference=phase2,
                message_id=phase2.message_id,
                thread_id=phase2.thread_id,
                provider_message_id=phase2.provider_message_id,
                provider_thread_id=phase2.provider_thread_id,
                rfc_message_id=phase2.rfc_message_id,
                subject=phase2.subject,
                sender_name=phase2.sender_name,
                sender_email=phase2.sender_email,
                sender_domain=phase2.sender_domain,
                sender_identity=self._sender_identity(phase2.sender_name, phase2.sender_domain),
                vendor_identity=self._vendor_identity(phase2.sender_domain),
                scrubbed_text=phase2.scrubbed_text,
                normalized_lines=list(phase2.normalized_lines),
                extracted_links=list(phase2.extracted_links),
                stage_statuses={"intake": "success"},
                stage_diagnostics={"intake": self._diagnostics(diagnostics)},
            ),
            None,
        )

    def generate_candidates(
        self,
        working: GmailPhase3WorkingEmail,
    ) -> tuple[list[GmailPhase3ProfileCandidate], list[str]]:
        signals = self._signal_terms()
        subject = (working.subject or "").lower()
        text = working.scrubbed_text.lower()
        lines = "\n".join(working.normalized_lines).lower()
        vendor = working.vendor_identity
        sender_domain = working.sender_domain or ""
        candidates: dict[str, list[str]] = {}

        def add(profile_id: str, reason: str) -> None:
            candidates.setdefault(profile_id, []).append(reason)

        if vendor == "amazon" and self._contains_any(subject, signals["amazon_confirmation_subject_terms"]):
            add("amazon_order_confirmation", "sender_domain:amazon_confirmation_subject")
        if vendor == "amazon" and self._contains_any(subject, signals["amazon_status_subject_terms"]):
            add("amazon_order_status_update", "sender_domain:amazon_status_subject")
        if vendor == "amazon" and "cancel" in subject:
            add("amazon_order_cancellation", "subject:cancellation")
        if self._contains_any(subject, signals["pickup_ready_terms"]) or self._contains_any(text, signals["pickup_ready_terms"]):
            add("pickup_ready_notification", "pickup_language:ready_for_pickup")
        if self._contains_any(subject, signals["curbside_terms"]) or self._contains_any(text, signals["curbside_terms"]):
            add("curbside_pickup_order", "pickup_language:curbside")
        if self._contains_any(subject, signals["reservation_terms"]) or self._contains_any(text, signals["reservation_terms"]) or self._contains_any(lines, signals["reservation_terms"]):
            add("reservation_confirmation", "reservation_language:confirmed")
        if self._contains_any(subject, signals["upcoming_subject_terms"]) and "order" in subject:
            add("upcoming_order_notice", "subject:upcoming_order")
        if self._contains_any(text, signals["upcoming_text_terms"]):
            add("upcoming_order_notice", "body:pending_order")
        if self._contains_any(subject, signals["confirmation_terms"]) or self._contains_any(text, signals["confirmation_terms"]):
            add("generic_order_confirmation", "confirmation_language")
        if self._contains_any(subject, signals["status_terms"]) or self._contains_any(text, signals["status_terms"]):
            add("generic_order_status_update", "status_language")
        if self._contains_any(subject, signals["cancellation_terms"]) or self._contains_any(text, signals["cancellation_terms"]):
            add("generic_order_cancellation", "cancellation_language")
        has_cancellation = self._contains_any(subject, signals["cancellation_terms"]) or self._contains_any(text, signals["cancellation_terms"])
        if (self._contains_any(subject, signals["ride_terms"]) or self._contains_any(text, signals["ride_terms"])) and not has_cancellation:
            add("ride_receipt", "ride_language")
        if (self._contains_any(subject, signals["ride_cancellation_terms"]) or self._contains_any(text, signals["ride_cancellation_terms"])) and has_cancellation:
            add("ride_cancellation", "ride_cancellation_language")

        sender_domain_profiles = self.rules.get("sender_domain_profiles", {})
        if isinstance(sender_domain_profiles, dict):
            mapped_profile = sender_domain_profiles.get(sender_domain)
            if isinstance(mapped_profile, str) and mapped_profile in self.taxonomy:
                add(mapped_profile, f"sender_domain:{sender_domain.replace('.', '_')}")

        diagnostics: list[str] = []
        candidate_models: list[GmailPhase3ProfileCandidate] = []
        for profile_id, reasons in candidates.items():
            taxonomy = self.taxonomy[profile_id]
            diagnostics.append(f"candidate:{profile_id} reasons={','.join(reasons)}")
            candidate_models.append(
                GmailPhase3ProfileCandidate(
                    profile_id=profile_id,
                    profile_family=str(taxonomy["profile_family"]),
                    profile_subtype=str(taxonomy["profile_subtype"]),
                    vendor_identity=(str(taxonomy["vendor_identity"]) if taxonomy["vendor_identity"] else vendor),
                    sender_identity=working.sender_identity,
                    reasons=reasons,
                )
            )

        if not candidate_models:
            diagnostics.append("candidate_generation:no_candidates")
        return candidate_models, diagnostics

    def score_candidates(
        self,
        working: GmailPhase3WorkingEmail,
        candidates: list[GmailPhase3ProfileCandidate],
    ) -> tuple[list[GmailPhase3ProfileCandidate], list[str]]:
        signals = self._signal_terms()
        weights = self._weights()
        thresholds = self._thresholds()
        diagnostics: list[str] = []
        ranked: list[GmailPhase3ProfileCandidate] = []
        subject = (working.subject or "").lower()
        text = working.scrubbed_text.lower()
        vendor = working.vendor_identity
        has_order_id = bool(ORDER_ID_PATTERN.search(working.scrubbed_text))
        has_pickup = "pickup" in subject or "pickup" in text
        has_curbside = "curbside" in subject or "curbside" in text
        has_reservation = "reservation" in subject or "reservation" in text
        has_upcoming = self._contains_any(subject, signals["upcoming_subject_terms"]) or self._contains_any(text, signals["upcoming_text_terms"])
        has_status = self._contains_any(text, signals["status_terms"]) or self._contains_any(subject, signals["status_terms"]) or "ordered" in text or "ordered" in subject
        has_cancellation = self._contains_any(subject, signals["cancellation_terms"]) or self._contains_any(text, signals["cancellation_terms"])
        has_ride = self._contains_any(text, signals["ride_terms"]) or self._contains_any(subject, signals["ride_terms"])

        for candidate in candidates:
            score = 0
            reasons = list(candidate.reasons)
            if candidate.vendor_identity and candidate.vendor_identity == vendor:
                score += weights["sender_match"]
                reasons.append("score:sender_match")
            if candidate.profile_id.startswith("amazon_") and vendor == "amazon":
                score += weights["amazon_vendor_profile"]
                reasons.append("score:amazon_vendor_profile")
            if candidate.profile_subtype == "confirmation" and any(token in subject for token in ("ordered:", "order confirmation", "thanks for")):
                score += weights["confirmation_subject"]
                reasons.append("score:confirmation_subject")
            if candidate.profile_subtype == "status_update" and has_status:
                score += weights["status_language"]
                reasons.append("score:status_language")
            if candidate.profile_subtype == "pickup_ready" and has_pickup:
                score += weights["pickup_language"]
                reasons.append("score:pickup_language")
            if candidate.profile_subtype == "curbside_ready" and has_curbside:
                score += weights["curbside_language"]
                reasons.append("score:curbside_language")
            if candidate.profile_subtype == "reservation_confirmed" and has_reservation:
                score += weights["reservation_language"]
                reasons.append("score:reservation_language")
            if candidate.profile_subtype == "upcoming_order" and has_upcoming:
                score += weights["upcoming_language"]
                reasons.append("score:upcoming_language")
            if candidate.profile_subtype == "cancellation" and has_cancellation:
                score += weights["cancellation_language"]
                reasons.append("score:cancellation_language")
            if candidate.profile_subtype == "ride_receipt" and has_ride:
                score += weights["ride_language"]
                reasons.append("score:ride_language")
            if candidate.profile_subtype == "ride_cancellation" and has_ride and has_cancellation:
                score += weights["ride_cancellation_language"]
                reasons.append("score:ride_cancellation_language")
            if has_order_id:
                score += weights["order_identifier_present"]
                reasons.append("score:order_identifier_present")
            if self._contains_any(text, signals["transactional_terms"]):
                score += weights["transactional_fields_present"]
                reasons.append("score:transactional_fields_present")
            if has_ride and self._contains_any(text, signals["ride_transactional_terms"]):
                score += weights["ride_transactional_fields"]
                reasons.append("score:ride_transactional_fields")

            confidence_level = "high" if score >= thresholds["high_score"] else "medium" if score >= thresholds["medium_score"] else "low"
            ranked.append(candidate.model_copy(update={"score": score, "confidence_level": confidence_level, "reasons": reasons}))
            diagnostics.append(f"scored:{candidate.profile_id} score={score} reasons={','.join(reasons[-5:])}")

        ranked.sort(key=lambda item: (item.score, len(item.reasons)), reverse=True)
        return ranked, diagnostics

    def resolve_profile(
        self,
        working: GmailPhase3WorkingEmail,
        ranked: list[GmailPhase3ProfileCandidate],
    ) -> tuple[GmailPhase3ProfileCandidate | None, list[GmailPhase3ProfileCandidate], float, str, list[str], str]:
        if not ranked:
            return None, [], 0.0, "low", ["profile_resolution:no_ranked_candidates"], "failed"

        primary = ranked[0]
        fallbacks = ranked[1:4]
        diagnostics = [f"resolved_profile:{primary.profile_id} score={primary.score}"]
        thresholds = self._thresholds()
        conflicts = self._conflicts()
        confidence = min(1.0, max(thresholds["min_confidence"], primary.score / thresholds["max_score"]))
        confidence_level = primary.confidence_level
        profile_status = "success" if confidence_level == "high" else "partial"

        if fallbacks and primary.score - fallbacks[0].score <= conflicts["close_competing_score_gap"]:
            confidence_level = "medium" if confidence_level == "high" else "low"
            confidence = max(thresholds["min_confidence_after_downgrade"], confidence - conflicts["close_competing_confidence_penalty"])
            profile_status = "partial"
            diagnostics.append("confidence_downgrade:close_competing_candidates")

        if self._has_conflicting_state_signals(working.scrubbed_text, working.subject or ""):
            confidence_level = "medium" if confidence_level == "high" else "low"
            confidence = max(thresholds["min_confidence_after_downgrade"], confidence - conflicts["conflicting_state_penalty"])
            profile_status = "partial"
            diagnostics.append("confidence_downgrade:conflicting_state_signals")

        if primary.score < 8:
            profile_status = "partial"
            diagnostics.append("confidence_downgrade:weak_primary_score")

        return primary, fallbacks, round(confidence, 2), confidence_level, diagnostics, profile_status

    @staticmethod
    def _contains_any(text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)

    def _has_conflicting_state_signals(self, text: str, subject: str) -> bool:
        lowered = f"{subject}\n{text}".lower()
        conflicts = self._conflicts()
        ignore_rules = conflicts["ignore_when_any_terms_present"]
        for pair in conflicts["pairs"]:
            if not all(term in lowered for term in pair):
                continue
            should_ignore = False
            for rule in ignore_rules:
                if rule["pair"] == pair and any(term in lowered for term in rule["any_terms"]):
                    should_ignore = True
                    break
            if not should_ignore:
                return True
        return False

    def _signal_terms(self) -> dict[str, list[str]]:
        signals = self.rules.get("signals", {})
        if not isinstance(signals, dict):
            return {}
        return {key: [str(item).lower() for item in value] for key, value in signals.items() if isinstance(value, list)}

    def _weights(self) -> dict[str, int]:
        weights = self.rules.get("weights", {})
        if not isinstance(weights, dict):
            return {}
        return {key: int(value) for key, value in weights.items() if isinstance(value, (int, float))}

    def _thresholds(self) -> dict[str, float]:
        thresholds = self.rules.get("thresholds", {})
        if not isinstance(thresholds, dict):
            return {}
        return {key: float(value) for key, value in thresholds.items() if isinstance(value, (int, float))}

    def _conflicts(self) -> dict[str, object]:
        raw = self.rules.get("conflicts", {})
        if not isinstance(raw, dict):
            return {
                "pairs": [],
                "ignore_when_any_terms_present": [],
                "close_competing_score_gap": 2,
                "close_competing_confidence_penalty": 0.2,
                "conflicting_state_penalty": 0.15,
            }
        pairs: list[list[str]] = []
        for item in raw.get("pairs", []):
            if isinstance(item, list):
                pairs.append([str(part).lower() for part in item])
        ignore_rules: list[dict[str, list[str]]] = []
        for item in raw.get("ignore_when_any_terms_present", []):
            if isinstance(item, dict):
                pair = item.get("pair")
                any_terms = item.get("any_terms")
                if isinstance(pair, list) and isinstance(any_terms, list):
                    ignore_rules.append(
                        {
                            "pair": [str(part).lower() for part in pair],
                            "any_terms": [str(term).lower() for term in any_terms],
                        }
                    )
        return {
            "pairs": pairs,
            "ignore_when_any_terms_present": ignore_rules,
            "close_competing_score_gap": int(raw.get("close_competing_score_gap", 2)),
            "close_competing_confidence_penalty": float(raw.get("close_competing_confidence_penalty", 0.2)),
            "conflicting_state_penalty": float(raw.get("conflicting_state_penalty", 0.15)),
        }

    @staticmethod
    def _sender_identity(sender_name: str | None, sender_domain: str | None) -> str | None:
        if sender_name and sender_domain:
            return f"{sender_name} <{sender_domain}>"
        return sender_name or sender_domain

    def _vendor_identity(self, sender_domain: str | None) -> str | None:
        if not sender_domain:
            return None
        return self.known_vendor_identities.get(sender_domain.lower(), sender_domain.split(".")[0].replace("-", "_"))

    @staticmethod
    def _diagnostics(items: list[str]) -> list[GmailPhase1DiagnosticItem]:
        diagnostics: list[GmailPhase1DiagnosticItem] = []
        for item in items:
            code = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_") or "diagnostic"
            diagnostics.append(GmailPhase1DiagnosticItem(code=code, detail=item))
        return diagnostics
