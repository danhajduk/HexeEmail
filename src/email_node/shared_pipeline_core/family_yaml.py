from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
import yaml


FlowFamilyYamlName = Literal["order", "action_required", "financial"]


class FamilyRuntimePathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_dir: str
    probation_template_dir: str
    probation_state_dir: str
    probation_evaluations_dir: str
    probation_shadow_dir: str
    output_dir: str
    reports_dir: str | None = None


class FamilyHeuristicsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ignore_line_patterns: list[str] = Field(default_factory=list)
    stop_marker_patterns: list[str] = Field(default_factory=list)
    chrome_line_patterns: list[str] = Field(default_factory=list)
    footer_cutoff_patterns: list[str] = Field(default_factory=list)
    important_link_patterns: dict[str, str] = Field(default_factory=dict)
    tracking_host_patterns: list[str] = Field(default_factory=list)
    filler_entity_patterns: list[str] = Field(default_factory=list)
    transactional_anchor_patterns: list[str] = Field(default_factory=list)
    promo_marker_patterns: list[str] = Field(default_factory=list)


class FamilyProfileTaxonomyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_family: str
    profile_subtype: str
    vendor_identity: str | None = None


class FamilyConflictIgnoreRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair: list[str] = Field(min_length=2, max_length=2)
    any_terms: list[str] = Field(default_factory=list)


class FamilyConflictRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairs: list[list[str]] = Field(default_factory=list)
    ignore_when_any_terms_present: list[FamilyConflictIgnoreRule] = Field(default_factory=list)
    close_competing_score_gap: int = 2
    close_competing_confidence_penalty: float = 0.2
    conflicting_state_penalty: float = 0.15


class FamilyProfileRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    signals: dict[str, list[str]] = Field(default_factory=dict)
    sender_domain_profiles: dict[str, str] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    conflicts: FamilyConflictRulesConfig


class FamilyProfilesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomy_version: str
    taxonomy: dict[str, FamilyProfileTaxonomyEntry] = Field(default_factory=dict)
    known_vendor_identities: dict[str, str] = Field(default_factory=dict)
    rules_override_path: str | None = None
    rules: FamilyProfileRulesConfig


class FamilyValidationPolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url_field_suffixes: list[str] = Field(default_factory=list)
    identifier_fields: list[str] = Field(default_factory=list)
    identifier_min_length: int = 1
    success_threshold: float = 0.85
    partial_threshold: float = 0.5
    required_field_confidence_weight: float = 0.6
    valid_field_confidence_weight: float = 0.4


class FamilyDecisionPolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.6


class FamilyActionFieldRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_fields: list[str] = Field(default_factory=list)
    any_of_fields: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)


class FamilyActionRoutingPolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_intents: dict[str, list[str]] = Field(default_factory=dict)
    decision_intents: dict[str, list[str]] = Field(default_factory=dict)
    diagnostic_token_intents: dict[str, list[str]] = Field(default_factory=dict)
    field_rules: list[FamilyActionFieldRuleConfig] = Field(default_factory=list)


class FlowFamilyYamlDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["flow-family-config.v1"] = "flow-family-config.v1"
    flow_family: FlowFamilyYamlName
    output_schema_family: str
    runtime_paths: FamilyRuntimePathsConfig
    heuristics: FamilyHeuristicsConfig
    profiles: FamilyProfilesConfig
    validation_policy: FamilyValidationPolicyConfig
    decision_policy: FamilyDecisionPolicyConfig
    action_routing_policy: FamilyActionRoutingPolicyConfig

    def resolve_runtime_path(self, key: str, *, runtime_dir: Path | None = None) -> Path:
        raw_value = getattr(self.runtime_paths, key)
        if not isinstance(raw_value, str):
            raise ValueError(f"Unsupported runtime path key: {key}")
        base_runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
        relative = Path(raw_value)
        return relative if relative.is_absolute() else base_runtime_dir / relative


def is_yaml_family_reference(reference: str) -> bool:
    return reference.startswith("yaml://")


def parse_yaml_family_reference(reference: str) -> FlowFamilyYamlName:
    if not is_yaml_family_reference(reference):
        raise ValueError(f"Not a YAML family reference: {reference}")
    family_name = reference.removeprefix("yaml://").strip()
    if family_name == "action_needed":
        return "action_required"
    if family_name not in {"order", "action_required", "financial"}:
        raise ValueError(f"Unsupported YAML family reference: {reference}")
    return family_name  # type: ignore[return-value]


def resolve_family_yaml_path(flow_family: FlowFamilyYamlName | str, *, runtime_dir: Path | None = None) -> Path:
    canonical_flow_family = _canonicalize_yaml_flow_family(flow_family)
    requested_runtime_dir = Path(runtime_dir) if runtime_dir is not None else None
    candidates: list[Path] = []
    if requested_runtime_dir is not None:
        candidates.append(requested_runtime_dir / "flow_families" / canonical_flow_family / "family.yaml")
    repo_runtime = _repo_root() / "runtime"
    candidates.append(repo_runtime / "flow_families" / canonical_flow_family / "family.yaml")
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def load_flow_family_yaml_definition(flow_family: FlowFamilyYamlName | str, *, runtime_dir: Path | None = None) -> FlowFamilyYamlDefinition:
    canonical_flow_family = _canonicalize_yaml_flow_family(flow_family)
    path = resolve_family_yaml_path(canonical_flow_family, runtime_dir=runtime_dir)
    if not path.exists():
        raise FileNotFoundError(f"Flow-family YAML was not found for {canonical_flow_family}: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Flow-family YAML must be a mapping: {path}")
    definition = FlowFamilyYamlDefinition.model_validate(payload)
    if definition.flow_family != canonical_flow_family:
        raise ValueError(f"Flow-family YAML mismatch: expected {canonical_flow_family}, found {definition.flow_family}")
    return definition


def build_scrub_heuristic_pack_from_yaml(
    definition: FlowFamilyYamlDefinition,
):
    from email_node.shared_pipeline_core.scrub_types import SharedScrubHeuristicPack

    heuristics = definition.heuristics
    return SharedScrubHeuristicPack(
        ignore_line_patterns=_compile_list(heuristics.ignore_line_patterns),
        stop_marker_patterns=_compile_list(heuristics.stop_marker_patterns),
        chrome_line_patterns=_compile_list(heuristics.chrome_line_patterns),
        footer_cutoff_patterns=_compile_list(heuristics.footer_cutoff_patterns),
        important_link_patterns={key: re.compile(pattern, re.IGNORECASE) for key, pattern in heuristics.important_link_patterns.items()},
        tracking_host_patterns=_compile_list(heuristics.tracking_host_patterns),
        filler_entity_patterns=_compile_list(heuristics.filler_entity_patterns),
        transactional_anchor_patterns=_compile_list(heuristics.transactional_anchor_patterns),
        promo_marker_patterns=_compile_list(heuristics.promo_marker_patterns),
    )


def build_profile_definition_pack_from_yaml(
    definition: FlowFamilyYamlDefinition,
    *,
    runtime_dir: Path | None = None,
):
    from email_node.shared_pipeline_core.profile_packs import SharedProfileDefinitionPack

    return SharedProfileDefinitionPack(
        flow_family=definition.flow_family,
        taxonomy_version=definition.profiles.taxonomy_version,
        taxonomy={
            key: value.model_dump(mode="json")
            for key, value in definition.profiles.taxonomy.items()
        },
        known_vendor_identities=dict(definition.profiles.known_vendor_identities),
        default_rules=definition.profiles.rules.model_dump(mode="json"),
        runtime_rules_path=(
            _resolve_relative_runtime_path(definition.profiles.rules_override_path, runtime_dir=runtime_dir)
            if definition.profiles.rules_override_path
            else Path("/__yaml_backed_family_rules__.json")
        ),
        runtime_rules_loader=lambda: definition.profiles.rules.model_dump(mode="json"),
    )


def build_validation_policy_from_yaml(definition: FlowFamilyYamlDefinition):
    from email_node.shared_pipeline_core.validation import SharedValidationPolicy

    payload = definition.validation_policy.model_dump(mode="json")
    return SharedValidationPolicy.from_mapping(payload)


def build_decision_policy_from_yaml(definition: FlowFamilyYamlDefinition):
    from email_node.shared_pipeline_core.decision import SharedDecisionPolicy

    payload = definition.decision_policy.model_dump(mode="json")
    return SharedDecisionPolicy(**payload)


def build_action_routing_policy_from_yaml(definition: FlowFamilyYamlDefinition):
    from email_node.shared_pipeline_core.actions import SharedActionFieldRule, SharedActionRoutingPolicy

    policy = definition.action_routing_policy
    return SharedActionRoutingPolicy(
        profile_intents={key: tuple(value) for key, value in policy.profile_intents.items()},
        decision_intents={key: tuple(value) for key, value in policy.decision_intents.items()},
        diagnostic_token_intents={key: tuple(value) for key, value in policy.diagnostic_token_intents.items()},
        field_rules=tuple(
            SharedActionFieldRule(
                required_fields=tuple(rule.required_fields),
                any_of_fields=tuple(rule.any_of_fields),
                intents=tuple(rule.intents),
            )
            for rule in policy.field_rules
        ),
    )


def _compile_list(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


def _resolve_relative_runtime_path(raw_value: str, *, runtime_dir: Path | None = None) -> Path:
    base_runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
    relative = Path(raw_value)
    return relative if relative.is_absolute() else base_runtime_dir / relative


def _canonicalize_yaml_flow_family(flow_family: FlowFamilyYamlName | str) -> FlowFamilyYamlName:
    if flow_family == "action_needed":
        return "action_required"
    if flow_family in {"order", "action_required", "financial"}:
        return flow_family  # type: ignore[return-value]
    raise ValueError(f"Unsupported flow family: {flow_family}")


def build_flow_family_config_from_yaml(
    definition: FlowFamilyYamlDefinition,
    *,
    runtime_dir: Path | None = None,
):
    from email_node.shared_pipeline_core.families import FlowFamilyConfig

    return FlowFamilyConfig(
        flow_family=definition.flow_family,
        scrub_heuristic_pack=f"yaml://{definition.flow_family}",
        profile_detector_pack=f"yaml://{definition.flow_family}",
        template_dir=definition.resolve_runtime_path("template_dir", runtime_dir=runtime_dir),
        probation_template_dir=definition.resolve_runtime_path("probation_template_dir", runtime_dir=runtime_dir),
        probation_state_dir=definition.resolve_runtime_path("probation_state_dir", runtime_dir=runtime_dir),
        probation_evaluations_dir=definition.resolve_runtime_path("probation_evaluations_dir", runtime_dir=runtime_dir),
        probation_shadow_dir=definition.resolve_runtime_path("probation_shadow_dir", runtime_dir=runtime_dir),
        validation_policy=f"yaml://{definition.flow_family}",
        decision_policy=f"yaml://{definition.flow_family}",
        action_router_policy=f"yaml://{definition.flow_family}",
        output_schema_family=definition.output_schema_family,
        output_dir=definition.resolve_runtime_path("output_dir", runtime_dir=runtime_dir),
        reports_dir=(
            definition.resolve_runtime_path("reports_dir", runtime_dir=runtime_dir)
            if definition.runtime_paths.reports_dir
            else None
        ),
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
