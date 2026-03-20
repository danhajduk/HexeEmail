from __future__ import annotations

import pytest
from pydantic import ValidationError

from config import AppConfig


def test_config_requires_email_node_type(tmp_path):
    with pytest.raises(ValidationError):
        AppConfig(
            CORE_BASE_URL="http://core.test",
            NODE_NAME="node",
            NODE_TYPE="gmail-node",
            NODE_SOFTWARE_VERSION="0.1.0",
            NODE_NONCE="nonce",
            RUNTIME_DIR=tmp_path,
        )


def test_config_exposes_provider_placeholders(config: AppConfig):
    assert config.providers.gmail.enabled is False
    assert config.providers.smtp.enabled is False
    assert config.providers.imap.enabled is False
