from __future__ import annotations

import re


IGNORE_LINE_PATTERNS = [
    re.compile(r"^\s*view (this )?(email|message) in your browser\s*$", re.IGNORECASE),
    re.compile(r"^\s*manage (preferences|email preferences)\s*$", re.IGNORECASE),
    re.compile(r"^\s*unsubscribe\s*$", re.IGNORECASE),
    re.compile(r"^\s*download the amazon app\s*$", re.IGNORECASE),
]

STOP_MARKER_PATTERNS = [
    re.compile(r"^\s*privacy notice\s*$", re.IGNORECASE),
    re.compile(r"^\s*conditions of use\s*$", re.IGNORECASE),
    re.compile(r"^\s*terms and conditions\s*$", re.IGNORECASE),
]

CHROME_LINE_PATTERNS = [
    re.compile(r"^\s*your orders\s*$", re.IGNORECASE),
    re.compile(r"^\s*your account\s*$", re.IGNORECASE),
    re.compile(r"^\s*buy again\s*$", re.IGNORECASE),
    re.compile(r"^\s*shop now\s*$", re.IGNORECASE),
]

FOOTER_CUTOFF_PATTERNS = [
    re.compile(r"copyright\s+\d{4}", re.IGNORECASE),
    re.compile(r"privacy notice", re.IGNORECASE),
    re.compile(r"conditions of use", re.IGNORECASE),
    re.compile(r"tax (invoice|disclosure|information)", re.IGNORECASE),
    re.compile(r"license|legal", re.IGNORECASE),
]

IMPORTANT_LINK_PATTERNS = {
    "tracking_action": re.compile(r"track|shipment|package", re.IGNORECASE),
    "order_action": re.compile(r"view or edit order|order details|your-orders|order|purchase", re.IGNORECASE),
    "account": re.compile(r"activate|account|sign in|signin", re.IGNORECASE),
    "document_action": re.compile(r"invoice|receipt|document|pdf", re.IGNORECASE),
}

TRACKING_HOST_PATTERNS = [
    re.compile(r"amazon-adsystem|doubleclick|google-analytics", re.IGNORECASE),
    re.compile(r"/open|/track|/pixel", re.IGNORECASE),
]

FILLER_ENTITY_PATTERNS = [
    re.compile(r"(?:&zwnj;|&nbsp;|&#8199;|&shy;|\u200c|\u00a0){3,}", re.IGNORECASE),
]

TRANSACTIONAL_ANCHOR_PATTERNS = [
    re.compile(r"thanks for your order", re.IGNORECASE),
    re.compile(r"\border\s*#", re.IGNORECASE),
    re.compile(r"arriving", re.IGNORECASE),
    re.compile(r"quantity", re.IGNORECASE),
    re.compile(r"grand total", re.IGNORECASE),
    re.compile(r"view or edit order", re.IGNORECASE),
]

PROMO_MARKER_PATTERNS = [
    re.compile(r"\b\d+%\s+off\b", re.IGNORECASE),
    re.compile(r"deals? for you", re.IGNORECASE),
    re.compile(r"recommended for you", re.IGNORECASE),
    re.compile(r"buy again", re.IGNORECASE),
    re.compile(r"shop similar", re.IGNORECASE),
]
