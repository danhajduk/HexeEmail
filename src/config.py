from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(BaseModel):
    enabled: bool = False


class ProviderConfigs(BaseModel):
    gmail: ProviderConfig = Field(default_factory=ProviderConfig)
    smtp: ProviderConfig = Field(default_factory=ProviderConfig)
    imap: ProviderConfig = Field(default_factory=ProviderConfig)


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    core_base_url: str = Field(alias="CORE_BASE_URL")
    node_name: str = Field(alias="NODE_NAME")
    node_type: str = Field(default="email-node", alias="NODE_TYPE")
    node_software_version: str = Field(alias="NODE_SOFTWARE_VERSION")
    node_nonce: str = Field(alias="NODE_NONCE")
    runtime_dir: Path = Field(default=Path("runtime"), alias="RUNTIME_DIR")
    onboarding_protocol_version: str = Field(default="1.0", alias="ONBOARDING_PROTOCOL_VERSION")
    onboarding_poll_interval_seconds: float = Field(default=2.0, alias="ONBOARDING_POLL_INTERVAL_SECONDS")
    mqtt_heartbeat_seconds: float = Field(default=30.0, alias="MQTT_HEARTBEAT_SECONDS")
    providers: ProviderConfigs = Field(default_factory=ProviderConfigs)

    @field_validator("core_base_url", "node_name", "node_software_version", "node_nonce")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        if value != "email-node":
            raise ValueError("NODE_TYPE must be email-node for Phase 1")
        return value

    @field_validator("runtime_dir")
    @classmethod
    def normalize_runtime_dir(cls, value: Path) -> Path:
        return value

    @property
    def state_file(self) -> Path:
        return self.runtime_dir / "state.json"

    @property
    def trust_material_file(self) -> Path:
        return self.runtime_dir / "trust_material.json"


class HealthSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    live: bool
    ready: bool
    version: str
    startup_error: str | None = None
