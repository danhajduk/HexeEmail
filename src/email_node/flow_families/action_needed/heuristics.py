from __future__ import annotations

import re


IGNORE_LINE_PATTERNS = [
    re.compile(r"^\s*view (this )?(email|message) in your browser\s*$", re.IGNORECASE),
    re.compile(r"^\s*manage (preferences|email preferences)\s*$", re.IGNORECASE),
    re.compile(r"^\s*unsubscribe\s*$", re.IGNORECASE),
]

STOP_MARKER_PATTERNS = [
    re.compile(r"^\s*privacy policy\s*$", re.IGNORECASE),
    re.compile(r"^\s*terms and conditions\s*$", re.IGNORECASE),
    re.compile(r"^\s*help center\s*$", re.IGNORECASE),
]

CHROME_LINE_PATTERNS = [
    re.compile(r"^\s*your account\s*$", re.IGNORECASE),
    re.compile(r"^\s*notification settings\s*$", re.IGNORECASE),
    re.compile(r"^\s*support center\s*$", re.IGNORECASE),
]

FOOTER_CUTOFF_PATTERNS = [
    re.compile(r"copyright\s+\d{4}", re.IGNORECASE),
    re.compile(r"privacy policy", re.IGNORECASE),
    re.compile(r"terms and conditions", re.IGNORECASE),
    re.compile(r"do not reply", re.IGNORECASE),
]

IMPORTANT_LINK_PATTERNS = {
    "account": re.compile(r"verify|confirm|sign|review|pay|resolve|reset", re.IGNORECASE),
    "document_action": re.compile(r"invoice|receipt|document|statement|pdf", re.IGNORECASE),
    "other": re.compile(r"account|sign in|signin|security", re.IGNORECASE),
}

TRACKING_HOST_PATTERNS = [
    re.compile(r"/open|/track|/pixel", re.IGNORECASE),
]

FILLER_ENTITY_PATTERNS = [
    re.compile(r"(?:&zwnj;|&nbsp;|&#8199;|&shy;|\u200c|\u00a0){3,}", re.IGNORECASE),
]

TRANSACTIONAL_ANCHOR_PATTERNS = [
    re.compile(r"action required", re.IGNORECASE),
    re.compile(r"payment due", re.IGNORECASE),
    re.compile(r"verify your account", re.IGNORECASE),
    re.compile(r"signature required", re.IGNORECASE),
    re.compile(r"confirm your", re.IGNORECASE),
    re.compile(r"deadline", re.IGNORECASE),
]

PROMO_MARKER_PATTERNS = [
    re.compile(r"recommended for you", re.IGNORECASE),
    re.compile(r"buy again", re.IGNORECASE),
    re.compile(r"shop now", re.IGNORECASE),
    re.compile(r"new features", re.IGNORECASE),
]
