from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


FlowFamily = Literal["order", "action_required", "financial", "invoice", "security", "shipment"]


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


def get_flow_family_config(flow_family: FlowFamily | str, *, runtime_dir: Path | None = None) -> FlowFamilyConfig:
    from email_node.shared_pipeline_core.family_yaml import (
        build_flow_family_config_from_yaml,
        load_flow_family_yaml_definition,
        resolve_family_yaml_path,
    )

    canonical_flow_family = _canonicalize_flow_family(flow_family)
    base_runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
    yaml_path = resolve_family_yaml_path(canonical_flow_family, runtime_dir=runtime_dir)
    if yaml_path.exists():
        definition = load_flow_family_yaml_definition(canonical_flow_family, runtime_dir=runtime_dir)
        return build_flow_family_config_from_yaml(definition, runtime_dir=runtime_dir)
    if canonical_flow_family == "order":
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
    if canonical_flow_family == "action_required":
        return FlowFamilyConfig(
            flow_family="action_required",
            scrub_heuristic_pack="email_node.flow_families.action_required.heuristics",
            profile_detector_pack="email_node.flow_families.action_required.profiles",
            template_dir=base_runtime_dir / "flow_families" / "action_required" / "templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "action_required" / "probation" / "templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "action_required" / "probation" / "state",
            probation_evaluations_dir=base_runtime_dir / "flow_families" / "action_required" / "probation" / "evaluations",
            probation_shadow_dir=base_runtime_dir / "flow_families" / "action_required" / "probation" / "shadow",
            validation_policy="email_node.flow_families.action_required.validation",
            decision_policy="email_node.flow_families.action_required.decision",
            action_router_policy="email_node.flow_families.action_required.action_routing",
            output_schema_family="action_required",
            output_dir=base_runtime_dir / "flow_families" / "action_required" / "outputs",
            reports_dir=base_runtime_dir / "flow_families" / "action_required" / "reports",
        )
    if canonical_flow_family == "financial":
        return FlowFamilyConfig(
            flow_family="financial",
            scrub_heuristic_pack="email_node.flow_families.financial.heuristics",
            profile_detector_pack="email_node.flow_families.financial.profiles",
            template_dir=base_runtime_dir / "flow_families" / "financial" / "templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "financial" / "probation" / "templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "financial" / "probation" / "state",
            probation_evaluations_dir=base_runtime_dir / "flow_families" / "financial" / "probation" / "evaluations",
            probation_shadow_dir=base_runtime_dir / "flow_families" / "financial" / "probation" / "shadow",
            validation_policy="email_node.flow_families.financial.validation",
            decision_policy="email_node.flow_families.financial.decision",
            action_router_policy="email_node.flow_families.financial.action_routing",
            output_schema_family="financial",
            output_dir=base_runtime_dir / "flow_families" / "financial" / "outputs",
            reports_dir=base_runtime_dir / "flow_families" / "financial" / "reports",
        )
    if canonical_flow_family == "invoice":
        return FlowFamilyConfig(
            flow_family="invoice",
            scrub_heuristic_pack="email_node.flow_families.invoice.heuristics",
            profile_detector_pack="email_node.flow_families.invoice.profiles",
            template_dir=base_runtime_dir / "flow_families" / "invoice" / "templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "invoice" / "probation" / "templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "invoice" / "probation" / "state",
            probation_evaluations_dir=base_runtime_dir / "flow_families" / "invoice" / "probation" / "evaluations",
            probation_shadow_dir=base_runtime_dir / "flow_families" / "invoice" / "probation" / "shadow",
            validation_policy="email_node.flow_families.invoice.validation",
            decision_policy="email_node.flow_families.invoice.decision",
            action_router_policy="email_node.flow_families.invoice.action_routing",
            output_schema_family="invoice",
            output_dir=base_runtime_dir / "flow_families" / "invoice" / "outputs",
            reports_dir=base_runtime_dir / "flow_families" / "invoice" / "reports",
        )
    if canonical_flow_family == "security":
        return FlowFamilyConfig(
            flow_family="security",
            scrub_heuristic_pack="email_node.flow_families.security.heuristics",
            profile_detector_pack="email_node.flow_families.security.profiles",
            template_dir=base_runtime_dir / "flow_families" / "security" / "templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "security" / "probation" / "templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "security" / "probation" / "state",
            probation_evaluations_dir=base_runtime_dir / "flow_families" / "security" / "probation" / "evaluations",
            probation_shadow_dir=base_runtime_dir / "flow_families" / "security" / "probation" / "shadow",
            validation_policy="email_node.flow_families.security.validation",
            decision_policy="email_node.flow_families.security.decision",
            action_router_policy="email_node.flow_families.security.action_routing",
            output_schema_family="security",
            output_dir=base_runtime_dir / "flow_families" / "security" / "outputs",
            reports_dir=base_runtime_dir / "flow_families" / "security" / "reports",
        )
    if canonical_flow_family == "shipment":
        return FlowFamilyConfig(
            flow_family="shipment",
            scrub_heuristic_pack="email_node.flow_families.shipment.heuristics",
            profile_detector_pack="email_node.flow_families.shipment.profiles",
            template_dir=base_runtime_dir / "flow_families" / "shipment" / "templates",
            probation_template_dir=base_runtime_dir / "flow_families" / "shipment" / "probation" / "templates",
            probation_state_dir=base_runtime_dir / "flow_families" / "shipment" / "probation" / "state",
            probation_evaluations_dir=base_runtime_dir / "flow_families" / "shipment" / "probation" / "evaluations",
            probation_shadow_dir=base_runtime_dir / "flow_families" / "shipment" / "probation" / "shadow",
            validation_policy="email_node.flow_families.shipment.validation",
            decision_policy="email_node.flow_families.shipment.decision",
            action_router_policy="email_node.flow_families.shipment.action_routing",
            output_schema_family="shipment",
            output_dir=base_runtime_dir / "flow_families" / "shipment" / "outputs",
            reports_dir=base_runtime_dir / "flow_families" / "shipment" / "reports",
        )
    raise ValueError(f"Unsupported flow family: {flow_family}")


def _canonicalize_flow_family(flow_family: FlowFamily | str) -> FlowFamily:
    if flow_family == "action_needed":
        return "action_required"
    if flow_family in {"order", "action_required", "financial", "invoice", "security", "shipment"}:
        return flow_family
    raise ValueError(f"Unsupported flow family: {flow_family}")
