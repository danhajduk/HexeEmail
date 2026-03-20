from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport

from email_node.config import AppConfig
from email_node.core_client import CoreApiClient


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
        ONBOARDING_POLL_INTERVAL_SECONDS=0.01,
        MQTT_HEARTBEAT_SECONDS=0.01,
    )


@pytest.fixture
def core_client_factory(config: AppConfig):
    def build(app):
        return CoreApiClient(config, transport=ASGITransport(app=app))

    return build
