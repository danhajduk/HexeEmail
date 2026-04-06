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
    probation_evaluations_dir: Path
    probation_shadow_dir: Path
    validation_policy: str
    decision_policy: str
    action_router_policy: str
    output_schema_family: str
    output_dir: Path
    reports_dir: Path | None = None


def get_flow_family_config(flow_family: FlowFamily, *, runtime_dir: Path | None = None) -> FlowFamilyConfig:
    from email_node.shared_pipeline_core.family_yaml import (
        build_flow_family_config_from_yaml,
        load_flow_family_yaml_definition,
        resolve_family_yaml_path,
    )

    base_runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
    yaml_path = resolve_family_yaml_path(flow_family, runtime_dir=runtime_dir)
    if yaml_path.exists():
        definition = load_flow_family_yaml_definition(flow_family, runtime_dir=runtime_dir)
        return build_flow_family_config_from_yaml(definition, runtime_dir=runtime_dir)
    if flow_family == "order":
        return FlowFamilyConfig(
            flow_family="order",
            scrub_heuristic_pack="email_node.flow_families.order.heuristics",
            profile_detector_pack="email_node.flow_families.order.profiles",
            template_dir=base_runtime_dir / "flow_families" / "order" / "templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "order" / "probation" / "templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "order" / "probation" / "state",
            probation_evaluations_dir=base_runtime_dir / "flow_families" / "order" / "probation" / "evaluations",
            probation_shadow_dir=base_runtime_dir / "flow_families" / "order" / "probation" / "shadow",
            validation_policy="email_node.flow_families.order.validation",
            decision_policy="email_node.flow_families.order.decision",
            action_router_policy="email_node.flow_families.order.action_routing",
            output_schema_family="order",
            output_dir=base_runtime_dir / "order_outputs",
            reports_dir=base_runtime_dir / "order_flow_logs" / "ad_hoc_reports",
        )
    if flow_family == "action_needed":
        return FlowFamilyConfig(
            flow_family="action_needed",
            scrub_heuristic_pack="email_node.flow_families.action_needed.heuristics",
            profile_detector_pack="email_node.flow_families.action_needed.profiles",
            template_dir=base_runtime_dir / "action_needed_templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "action_needed" / "probation_templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "action_needed" / "probation_state",
            probation_evaluations_dir=base_runtime_dir / "flow_families" / "action_needed" / "probation_evaluations",
            probation_shadow_dir=base_runtime_dir / "flow_families" / "action_needed" / "probation_shadow",
            validation_policy="email_node.flow_families.action_needed.validation",
            decision_policy="email_node.flow_families.action_needed.decision",
            action_router_policy="email_node.flow_families.action_needed.action_routing",
            output_schema_family="action_needed",
            output_dir=base_runtime_dir / "action_needed_outputs",
            reports_dir=base_runtime_dir / "flow_families" / "action_needed" / "reports",
        )
    raise ValueError(f"Unsupported flow family: {flow_family}")
