from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


DEFAULT_ORDER_PHASE3_RULES: dict[str, object] = {
    "schema_version": "order-phase3-rules.v1",
    "signals": {
        "amazon_confirmation_subject_terms": ["ordered:"],
        "amazon_status_subject_terms": ["shipped:", "delivered:", "arriving", "item cancelled"],
        "pickup_ready_terms": ["ready for pickup", "order is ready for pickup"],
        "curbside_terms": ["curbside pickup", "curbside"],
        "reservation_terms": ["reservation confirmation", "reservation details", "your reservation details"],
        "upcoming_subject_terms": ["upcoming"],
        "upcoming_text_terms": ["pending order"],
        "confirmation_terms": ["order confirmation", "thanks for your order", "thank you for your order"],
        "status_terms": ["shipped", "delivered", "arriving", "out for delivery"],
        "cancellation_terms": ["cancel", "cancelled", "cancellation"],
        "ride_terms": ["ride receipt", "your ride", "trip distance", "trip duration", "drop-off", "pickup:", "fare"],
        "ride_cancellation_terms": ["ride receipt", "your ride", "trip distance", "trip duration"],
        "transactional_terms": ["grand total", "quantity", "view or edit order", "reservation"],
        "ride_transactional_terms": ["trip total", "drop-off", "pickup:", "refund"],
    },
    "sender_domain_profiles": {
        "dutchie.com": "pickup_ready_notification",
        "walmart.com": "curbside_pickup_order",
        "recreation.gov": "reservation_confirmation",
        "edenredbenefits.com": "upcoming_order_notice",
    },
    "weights": {
        "sender_match": 5,
        "amazon_vendor_profile": 5,
        "confirmation_subject": 4,
        "status_language": 4,
        "pickup_language": 6,
        "curbside_language": 7,
        "reservation_language": 7,
        "upcoming_language": 7,
        "cancellation_language": 7,
        "ride_language": 8,
        "ride_cancellation_language": 10,
        "order_identifier_present": 2,
        "transactional_fields_present": 1,
        "ride_transactional_fields": 2,
    },
    "thresholds": {
        "high_score": 14,
        "medium_score": 8,
        "max_score": 20,
        "min_confidence": 0.05,
        "min_confidence_after_downgrade": 0.2,
    },
    "conflicts": {
        "pairs": [
            ["cancel", "pickup"],
            ["reservation", "curbside"],
        ],
        "ignore_when_any_terms_present": [
            {
                "pair": ["cancel", "pickup"],
                "any_terms": ["ride receipt", "your ride", "trip distance", "trip duration", "drop-off", "pickup:", "fare"],
            }
        ],
        "close_competing_score_gap": 2,
        "close_competing_confidence_penalty": 0.2,
        "conflicting_state_penalty": 0.15,
    },
}


class GmailOrderProfileRulesStore:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
        self.path = self.runtime_dir / "order_profile_rules.json"

    def load(self) -> dict[str, object]:
        rules = deepcopy(DEFAULT_ORDER_PHASE3_RULES)
        if not self.path.exists():
            return rules
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return rules
        return _deep_merge(rules, payload)


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = deepcopy(value)
    return merged
