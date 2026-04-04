from __future__ import annotations

import re
from typing import Any


BOUNDARY_PATTERN = re.compile(r'boundary="?([^";]+)"?', re.IGNORECASE)
CHARSET_PATTERN = re.compile(r'charset="?([^";]+)"?', re.IGNORECASE)


def normalize_headers(headers: object) -> dict[str, str]:
    if not isinstance(headers, list):
        return {}
    normalized: dict[str, str] = {}
    for header in headers:
        if not isinstance(header, dict):
            continue
        name = header.get("name")
        value = header.get("value")
        if isinstance(name, str) and isinstance(value, str):
            normalized[name.strip().lower()] = value
    return normalized


def extract_boundary(content_type: str | None) -> str | None:
    text = str(content_type or "").strip()
    if not text:
        return None
    match = BOUNDARY_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1).strip() or None


def extract_charset(content_type: str | None) -> str | None:
    text = str(content_type or "").strip()
    if not text:
        return None
    match = CHARSET_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1).strip() or None


def parse_mime_tree(payload: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {
            "status": "failed",
            "diagnostics": ["gmail payload is missing"],
            "mime_boundaries": [],
            "parts": [],
        }

    parts: list[dict[str, object]] = []
    boundaries: list[str] = []
    diagnostics: list[str] = []

    def visit(node: dict[str, Any], index_path: str) -> None:
        headers = normalize_headers(node.get("headers"))
        content_type = headers.get("content-type") or (str(node.get("mimeType") or "").strip() or None)
        mime_type = str(node.get("mimeType") or "").strip().lower() or "application/octet-stream"
        disposition = headers.get("content-disposition")
        filename = str(node.get("filename") or "").strip() or None
        boundary = extract_boundary(content_type)
        if boundary and boundary not in boundaries:
            boundaries.append(boundary)
        charset = extract_charset(content_type)
        body = node.get("body") if isinstance(node.get("body"), dict) else {}
        body_size = int(body.get("size") or 0) if isinstance(body, dict) else 0
        has_inline_body = bool(isinstance(body, dict) and body.get("data"))
        is_attachment = bool(filename) or ("attachment" in str(disposition or "").lower())
        parts.append(
            {
                "index": index_path,
                "mime_type": mime_type,
                "content_type": content_type,
                "content_transfer_encoding": headers.get("content-transfer-encoding"),
                "charset": charset,
                "content_disposition": disposition,
                "filename": filename,
                "is_attachment": is_attachment,
                "body_size": body_size,
                "has_inline_body": has_inline_body,
                "is_multipart": mime_type.startswith("multipart/"),
            }
        )
        child_parts = node.get("parts")
        if isinstance(child_parts, list) and child_parts:
            for child_index, child in enumerate(child_parts):
                if isinstance(child, dict):
                    visit(child, f"{index_path}.{child_index}")
                else:
                    diagnostics.append(f"invalid MIME child part at {index_path}.{child_index}")

    visit(payload, "0")
    status = "success"
    if not parts:
        status = "failed"
        diagnostics.append("no MIME parts were found")
    elif any(not isinstance(item.get("mime_type"), str) or not item.get("mime_type") for item in parts):
        status = "partial"
        diagnostics.append("one or more MIME parts were missing mime_type")
    return {
        "status": status,
        "diagnostics": diagnostics,
        "mime_boundaries": boundaries,
        "parts": parts,
    }
