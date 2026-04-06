from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


FlowFamily = Literal["order", "action_needed"]


@dataclass(frozen=True, slots=True)
class FlowFamilyConfig:
    flow_family: FlowFamily
    scrub_heuristic_pack: str
    profile_detector_pack: str
    template_dir: Path
    probation_template_dir: Path
    probation_state_dir: Path
    validation_policy: str
    decision_policy: str
    action_router_policy: str
    output_schema_family: str


def get_flow_family_config(flow_family: FlowFamily, *, runtime_dir: Path | None = None) -> FlowFamilyConfig:
    base_runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
    if flow_family == "order":
        return FlowFamilyConfig(
            flow_family="order",
            scrub_heuristic_pack="providers.gmail.order_scrubber_rules",
            profile_detector_pack="runtime/order_profile_rules.json",
            template_dir=base_runtime_dir / "order_templates",
            probation_template_dir=Path("src/email_node/patterns/probation"),
            probation_state_dir=Path("src/email_node/patterns/probation_state"),
            validation_policy="providers.gmail.order_validation",
            decision_policy="email_node.pipeline.order_decision_engine",
            action_router_policy="email_node.pipeline.order_action_router",
            output_schema_family="order",
        )
    if flow_family == "action_needed":
        return FlowFamilyConfig(
            flow_family="action_needed",
            scrub_heuristic_pack="runtime/flow_families/action_needed/heuristics",
            profile_detector_pack="runtime/flow_families/action_needed/profile_rules.json",
            template_dir=base_runtime_dir / "action_needed_templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "action_needed" / "probation_templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "action_needed" / "probation_state",
            validation_policy="runtime/flow_families/action_needed/validation_policy.json",
            decision_policy="runtime/flow_families/action_needed/decision_policy.json",
            action_router_policy="runtime/flow_families/action_needed/action_router_policy.json",
            output_schema_family="action_needed",
        )
    raise ValueError(f"Unsupported flow family: {flow_family}")
