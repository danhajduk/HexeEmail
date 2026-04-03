from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from logging.handlers import TimedRotatingFileHandler

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


class LoggerNameFilter(logging.Filter):
    def __init__(self, prefixes: tuple[str, ...], contains: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.prefixes = prefixes
        self.contains = contains

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        return any(name.startswith(prefix) for prefix in self.prefixes) or any(token in name for token in self.contains)


def _next_six_hour_boundary_epoch(now_epoch: float | None = None) -> int:
    now = datetime.fromtimestamp(now_epoch or time.time()).astimezone()
    boundary_hour = ((now.hour // 6) + 1) * 6
    if boundary_hour >= 24:
        next_boundary = now.replace(hour=0, minute=0, second=0, microsecond=0)
        next_boundary = next_boundary + timedelta(days=1)
    else:
        next_boundary = now.replace(hour=boundary_hour, minute=0, second=0, microsecond=0)
    return int(next_boundary.timestamp())


def _build_rotating_file_handler(path: Path, formatter: logging.Formatter) -> TimedRotatingFileHandler:
    handler = TimedRotatingFileHandler(
        path,
        when="H",
        interval=6,
        backupCount=20,
        encoding="utf-8",
    )
    handler.rolloverAt = _next_six_hour_boundary_epoch()
    handler.setFormatter(formatter)
    return handler


def setup_logging(level: int = logging.INFO) -> None:
    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    runtime_dir = Path.cwd() / "runtime"
    log_dir = runtime_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    all_handler = _build_rotating_file_handler(log_dir / "app.log", formatter)

    categorized_handlers: list[logging.Handler] = []
    categories = (
        ("api.log", ("main", "service", "uvicorn", "fastapi", "hexe.api", "test.api"), (".api",)),
        ("providers.log", ("providers.", "hexe.providers"), ()),
        ("core.log", ("core.", "core_client", "hexe.core"), ()),
        ("ai.log", ("hexe.ai",), ()),
        ("mqtt.log", ("mqtt", "hexe.mqtt"), ()),
    )
    for filename, prefixes, contains in categories:
        handler = _build_rotating_file_handler(log_dir / filename, formatter)
        handler.addFilter(LoggerNameFilter(prefixes=prefixes, contains=contains))
        categorized_handlers.append(handler)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(all_handler)
    for handler in categorized_handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    token = correlation_id_var.set(correlation_id)
    started = time.perf_counter()
    api_logger = get_logger("hexe.api.http")
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        api_logger.info(
            "HTTP request completed",
            extra={
                "event_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
        response.headers["X-Correlation-Id"] = correlation_id
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        api_logger.exception(
            "HTTP request failed",
            extra={
                "event_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                }
            },
        )
        raise
    finally:
        correlation_id_var.reset(token)
