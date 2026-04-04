from __future__ import annotations

import re
from datetime import datetime

from providers.gmail.models import (
    GmailPhase1DiagnosticItem,
    GmailPhase2ScrubbedEmail,
    GmailPhase3DetectedEmail,
    GmailPhase3NormalizationMetadata,
    GmailPhase3ProfileCandidate,
    GmailPhase3WorkingEmail,
)
from providers.gmail.order_profile_taxonomy import (
    KNOWN_VENDOR_IDENTITIES,
    PROFILE_TAXONOMY,
    PROFILE_TAXONOMY_VERSION,
)


PROFILE_DETECTOR_VERSION = "order-phase3-profile-detector.v1"
ORDER_ID_PATTERN = re.compile(r"\b\d{3}-\d{7}-\d{7}\b")


class GmailOrderPhase3ProfileDetector:
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
                    taxonomy_version=PROFILE_TAXONOMY_VERSION,
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
                taxonomy_version=PROFILE_TAXONOMY_VERSION,
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
        subject = (working.subject or "").lower()
        text = working.scrubbed_text.lower()
        lines = "\n".join(working.normalized_lines).lower()
        vendor = working.vendor_identity
        sender_domain = working.sender_domain or ""
        candidates: dict[str, list[str]] = {}

        def add(profile_id: str, reason: str) -> None:
            candidates.setdefault(profile_id, []).append(reason)

        if vendor == "amazon" and subject.startswith("ordered:"):
            add("amazon_order_confirmation", "sender_domain:amazon_confirmation_subject")
        if vendor == "amazon" and any(token in subject for token in ("shipped:", "delivered:", "arriving", "item cancelled")):
            add("amazon_order_status_update", "sender_domain:amazon_status_subject")
        if vendor == "amazon" and "cancel" in subject:
            add("amazon_order_cancellation", "subject:cancellation")
        if "ready for pickup" in subject or "ready for pickup" in text or "order is ready for pickup" in text:
            add("pickup_ready_notification", "pickup_language:ready_for_pickup")
        if "curbside pickup" in subject or "curbside" in text:
            add("curbside_pickup_order", "pickup_language:curbside")
        if "reservation confirmation" in subject or "reservation details" in text or "your reservation details" in lines:
            add("reservation_confirmation", "reservation_language:confirmed")
        if "upcoming" in subject and "order" in subject:
            add("upcoming_order_notice", "subject:upcoming_order")
        if "pending order" in text:
            add("upcoming_order_notice", "body:pending_order")
        if "order confirmation" in subject or "thanks for your order" in text or "thank you for your order" in text:
            add("generic_order_confirmation", "confirmation_language")
        if any(token in subject for token in ("shipped", "delivered", "arriving")) or any(
            token in text for token in ("shipped", "delivered", "arriving", "out for delivery")
        ):
            add("generic_order_status_update", "status_language")
        if "cancel" in subject or "cancelled" in text or "cancellation" in text:
            add("generic_order_cancellation", "cancellation_language")

        if sender_domain == "dutchie.com":
            add("pickup_ready_notification", "sender_domain:dutchie")
        if sender_domain == "walmart.com":
            add("curbside_pickup_order", "sender_domain:walmart")
        if sender_domain == "recreation.gov":
            add("reservation_confirmation", "sender_domain:recreation_gov")
        if sender_domain == "edenredbenefits.com":
            add("upcoming_order_notice", "sender_domain:edenred_benefits")

        diagnostics: list[str] = []
        candidate_models: list[GmailPhase3ProfileCandidate] = []
        for profile_id, reasons in candidates.items():
            taxonomy = PROFILE_TAXONOMY[profile_id]
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
        diagnostics: list[str] = []
        ranked: list[GmailPhase3ProfileCandidate] = []
        subject = (working.subject or "").lower()
        text = working.scrubbed_text.lower()
        vendor = working.vendor_identity
        has_order_id = bool(ORDER_ID_PATTERN.search(working.scrubbed_text))
        has_pickup = "pickup" in subject or "pickup" in text
        has_curbside = "curbside" in subject or "curbside" in text
        has_reservation = "reservation" in subject or "reservation" in text
        has_upcoming = "upcoming" in subject or "pending order" in text
        has_status = any(token in text or token in subject for token in ("shipped", "delivered", "arriving", "ordered"))
        has_cancellation = "cancel" in subject or "cancelled" in text

        for candidate in candidates:
            score = 0
            reasons = list(candidate.reasons)
            if candidate.vendor_identity and candidate.vendor_identity == vendor:
                score += 5
                reasons.append("score:sender_match")
            if candidate.profile_id.startswith("amazon_") and vendor == "amazon":
                score += 5
                reasons.append("score:amazon_vendor_profile")
            if candidate.profile_subtype == "confirmation" and any(token in subject for token in ("ordered:", "order confirmation", "thanks for")):
                score += 4
                reasons.append("score:confirmation_subject")
            if candidate.profile_subtype == "status_update" and has_status:
                score += 4
                reasons.append("score:status_language")
            if candidate.profile_subtype == "pickup_ready" and has_pickup:
                score += 6
                reasons.append("score:pickup_language")
            if candidate.profile_subtype == "curbside_ready" and has_curbside:
                score += 7
                reasons.append("score:curbside_language")
            if candidate.profile_subtype == "reservation_confirmed" and has_reservation:
                score += 7
                reasons.append("score:reservation_language")
            if candidate.profile_subtype == "upcoming_order" and has_upcoming:
                score += 7
                reasons.append("score:upcoming_language")
            if candidate.profile_subtype == "cancellation" and has_cancellation:
                score += 7
                reasons.append("score:cancellation_language")
            if has_order_id:
                score += 2
                reasons.append("score:order_identifier_present")
            if any(token in text for token in ("grand total", "quantity", "view or edit order", "reservation")):
                score += 1
                reasons.append("score:transactional_fields_present")

            confidence_level = "high" if score >= 14 else "medium" if score >= 8 else "low"
            ranked.append(candidate.model_copy(update={"score": score, "confidence_level": confidence_level, "reasons": reasons}))
            diagnostics.append(f"scored:{candidate.profile_id} score={score} reasons={','.join(reasons[-5:])}")

        ranked.sort(key=lambda item: (item.score, len(item.reasons)), reverse=True)
        return ranked, diagnostics

    def resolve_profile(
        self,
        working: GmailPhase3WorkingEmail,
        ranked: list[GmailPhase3ProfileCandidate],
    ) -> tuple[
        GmailPhase3ProfileCandidate | None,
        list[GmailPhase3ProfileCandidate],
        float,
        str,
        list[str],
        str,
    ]:
        if not ranked:
            return None, [], 0.0, "low", ["profile_resolution:no_ranked_candidates"], "failed"

        primary = ranked[0]
        fallbacks = ranked[1:4]
        diagnostics = [f"resolved_profile:{primary.profile_id} score={primary.score}"]
        confidence = min(1.0, max(0.05, primary.score / 20))
        confidence_level = primary.confidence_level
        profile_status = "success" if confidence_level == "high" else "partial"

        if fallbacks and primary.score - fallbacks[0].score <= 2:
            confidence_level = "medium" if confidence_level == "high" else "low"
            confidence = max(0.2, confidence - 0.2)
            profile_status = "partial"
            diagnostics.append("confidence_downgrade:close_competing_candidates")

        if self._has_conflicting_state_signals(working.scrubbed_text, working.subject or ""):
            confidence_level = "medium" if confidence_level == "high" else "low"
            confidence = max(0.2, confidence - 0.15)
            profile_status = "partial"
            diagnostics.append("confidence_downgrade:conflicting_state_signals")

        if primary.score < 8:
            profile_status = "partial"
            diagnostics.append("confidence_downgrade:weak_primary_score")

        return primary, fallbacks, round(confidence, 2), confidence_level, diagnostics, profile_status

    @staticmethod
    def _has_conflicting_state_signals(text: str, subject: str) -> bool:
        lowered = f"{subject}\n{text}".lower()
        return ("cancel" in lowered and "pickup" in lowered) or ("reservation" in lowered and "curbside" in lowered)

    @staticmethod
    def _sender_identity(sender_name: str | None, sender_domain: str | None) -> str | None:
        if sender_name and sender_domain:
            return f"{sender_name} <{sender_domain}>"
        return sender_name or sender_domain

    @staticmethod
    def _vendor_identity(sender_domain: str | None) -> str | None:
        if not sender_domain:
            return None
        return KNOWN_VENDOR_IDENTITIES.get(sender_domain.lower(), sender_domain.split(".")[0].replace("-", "_"))

    @staticmethod
    def _diagnostics(items: list[str]) -> list[GmailPhase1DiagnosticItem]:
        diagnostics: list[GmailPhase1DiagnosticItem] = []
        for item in items:
            code = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_") or "diagnostic"
            diagnostics.append(GmailPhase1DiagnosticItem(code=code, detail=item))
        return diagnostics
