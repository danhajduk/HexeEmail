from __future__ import annotations

import hashlib


def stable_text_hash(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
