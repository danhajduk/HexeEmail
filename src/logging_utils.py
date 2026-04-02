from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Request


correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

REDACTED_KEYS = {
    "node_trust_token",
    "operational_mqtt_token",
    "authorization",
    "x-node-trust-token",
}


def redact_value(key: str, value: Any) -> Any:
    if key.lower() in REDACTED_KEYS and value:
        return "***redacted***"
    if isinstance(value, dict):
        return {inner_key: redact_value(inner_key, inner_value) for inner_key, inner_value in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
        }
        extra = getattr(record, "event_data", None)
        if isinstance(extra, dict):
            payload["event"] = {key: redact_value(key, value) for key, value in extra.items()}
        return json.dumps(payload, sort_keys=True)


def setup_logging(level: int = logging.INFO) -> None:
    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    runtime_dir = Path.cwd() / "runtime"
    log_dir = runtime_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "api.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    token = correlation_id_var.set(correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
    finally:
        correlation_id_var.reset(token)
