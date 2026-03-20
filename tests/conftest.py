from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport

from config import AppConfig
from core_client import CoreApiClient


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    return runtime


@pytest.fixture
def config(runtime_dir: Path) -> AppConfig:
    return AppConfig(
        CORE_BASE_URL="http://core.test",
        NODE_NAME="email-node-test",
        NODE_TYPE="email-node",
        NODE_SOFTWARE_VERSION="0.1.0",
        NODE_NONCE="nonce-test",
        RUNTIME_DIR=runtime_dir,
        API_PORT=9003,
        UI_PORT=8083,
        ONBOARDING_POLL_INTERVAL_SECONDS=0.01,
        MQTT_HEARTBEAT_SECONDS=0.01,
    )


@pytest.fixture
def core_client_factory(config: AppConfig):
    def build(app):
        return CoreApiClient(transport=ASGITransport(app=app))

    return build
