from __future__ import annotations


PROFILE_TAXONOMY_VERSION = "order-phase3-taxonomy.v1"


PROFILE_TAXONOMY: dict[str, dict[str, str | None]] = {
    "amazon_order_confirmation": {
        "profile_family": "order",
        "profile_subtype": "confirmation",
        "vendor_identity": "amazon",
    },
    "amazon_order_status_update": {
        "profile_family": "order",
        "profile_subtype": "status_update",
        "vendor_identity": "amazon",
    },
    "amazon_order_cancellation": {
        "profile_family": "order",
        "profile_subtype": "cancellation",
        "vendor_identity": "amazon",
    },
    "pickup_ready_notification": {
        "profile_family": "order",
        "profile_subtype": "pickup_ready",
        "vendor_identity": None,
    },
    "curbside_pickup_order": {
        "profile_family": "order",
        "profile_subtype": "curbside_ready",
        "vendor_identity": None,
    },
    "reservation_confirmation": {
        "profile_family": "order",
        "profile_subtype": "reservation_confirmed",
        "vendor_identity": None,
    },
    "upcoming_order_notice": {
        "profile_family": "order",
        "profile_subtype": "upcoming_order",
        "vendor_identity": None,
    },
    "generic_order_confirmation": {
        "profile_family": "order",
        "profile_subtype": "confirmation",
        "vendor_identity": None,
    },
    "generic_order_status_update": {
        "profile_family": "order",
        "profile_subtype": "status_update",
        "vendor_identity": None,
    },
    "generic_order_cancellation": {
        "profile_family": "order",
        "profile_subtype": "cancellation",
        "vendor_identity": None,
    },
}


KNOWN_VENDOR_IDENTITIES: dict[str, str] = {
    "amazon.com": "amazon",
    "dutchie.com": "dutchie",
    "walmart.com": "walmart",
    "recreation.gov": "recreation_gov",
    "edenredbenefits.com": "edenred_benefits",
}
