from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OperatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_base_url: str | None = None
    node_name: str | None = None
    selected_task_capabilities: list[str] = Field(default_factory=list)


class OperatorConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_base_url: str | None = None
    node_name: str | None = None
    selected_task_capabilities: list[str] = Field(default_factory=list)


class TaskCapabilitySelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_task_capabilities: list[str] = Field(default_factory=list)
