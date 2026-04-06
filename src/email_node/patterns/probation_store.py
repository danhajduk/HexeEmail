from __future__ import annotations

import json
from pathlib import Path

from email_node.patterns.probation_state import ProbationTemplateState


class ProbationStore:
    def __init__(
        self,
        *,
        runtime_dir: Path | None = None,
        flow_family: str = "order",
        templates_dir: Path | None = None,
        state_dir: Path | None = None,
        evaluations_dir: Path | None = None,
        shadow_dir: Path | None = None,
    ) -> None:
        runtime_base_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")
        family_probation_dir = runtime_base_dir / "flow_families" / flow_family / "probation"
        base_dir = Path(__file__).resolve().parent
        legacy_templates_dir = base_dir / "probation"
        legacy_state_dir = base_dir / "probation_state"
        legacy_evaluations_dir = base_dir / "probation_evaluations"
        legacy_shadow_dir = base_dir / "probation_shadow"
        self.templates_dir = templates_dir or (family_probation_dir / "templates")
        self.state_dir = state_dir or (family_probation_dir / "state")
        self.evaluations_dir = evaluations_dir or (family_probation_dir / "evaluations")
        self.shadow_dir = shadow_dir or (family_probation_dir / "shadow")
        self.legacy_templates_dir = None if templates_dir is not None else legacy_templates_dir
        self.legacy_state_dir = None if state_dir is not None else legacy_state_dir
        self.legacy_evaluations_dir = None if evaluations_dir is not None else legacy_evaluations_dir
        self.legacy_shadow_dir = None if shadow_dir is not None else legacy_shadow_dir
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)
        self.shadow_dir.mkdir(parents=True, exist_ok=True)

    def build_template_path(self, template_id: str) -> Path:
        return self.templates_dir / f"{template_id}.json"

    def build_state_path(self, template_id: str) -> Path:
        return self.state_dir / f"{template_id}.json"

    def build_evaluation_path(self, template_id: str, message_id: str) -> Path:
        return self.evaluations_dir / template_id / f"{message_id}.json"

    def build_shadow_path(self, template_id: str, message_id: str) -> Path:
        return self.shadow_dir / template_id / f"{message_id}.json"

    def save_template_payload(self, template_id: str, payload: dict[str, object]) -> Path:
        path = self.build_template_path(template_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return path

    def load_template_payload(self, template_id: str) -> dict[str, object] | None:
        for path in self._candidate_template_paths(template_id):
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        return None

    def save_state(self, state: ProbationTemplateState) -> Path:
        path = self.build_state_path(state.template_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_state(self, template_id: str) -> ProbationTemplateState | None:
        for path in self._candidate_state_paths(template_id):
            if path.exists():
                return ProbationTemplateState.model_validate_json(path.read_text(encoding="utf-8"))
        return None

    def save_evaluation(self, evaluation) -> Path:
        path = self.build_evaluation_path(evaluation.template_id, evaluation.message_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(evaluation, "model_dump_json"):
            path.write_text(evaluation.model_dump_json(indent=2), encoding="utf-8")
        else:
            path.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
        return path

    def list_evaluations(self, template_id: str) -> list[dict[str, object]]:
        evaluations: list[dict[str, object]] = []
        seen_names: set[str] = set()
        for root in self._candidate_evaluation_roots(template_id):
            if not root.exists():
                continue
            for path in sorted(root.glob("*.json")):
                if path.name in seen_names:
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    evaluations.append(payload)
                    seen_names.add(path.name)
        return evaluations

    def save_shadow_comparison(self, template_id: str, message_id: str, payload: dict[str, object]) -> Path:
        path = self.build_shadow_path(template_id, message_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return path

    def list_shadow_comparisons(self, template_id: str) -> list[dict[str, object]]:
        comparisons: list[dict[str, object]] = []
        seen_names: set[str] = set()
        for root in self._candidate_shadow_roots(template_id):
            if not root.exists():
                continue
            for path in sorted(root.glob("*.json")):
                if path.name in seen_names:
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    comparisons.append(payload)
                    seen_names.add(path.name)
        return comparisons

    def list_states(self) -> list[ProbationTemplateState]:
        states: list[ProbationTemplateState] = []
        seen_names: set[str] = set()
        for root in self._candidate_state_roots():
            if not root.exists():
                continue
            for path in sorted(root.glob("*.json")):
                if path.name in seen_names:
                    continue
                states.append(ProbationTemplateState.model_validate_json(path.read_text(encoding="utf-8")))
                seen_names.add(path.name)
        return states

    def list_templates(self) -> list[dict[str, object]]:
        templates: list[dict[str, object]] = []
        seen_names: set[str] = set()
        for root in self._candidate_template_roots():
            if not root.exists():
                continue
            for path in sorted(root.glob("*.json")):
                if path.name in seen_names:
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    payload["_path"] = str(path)
                    templates.append(payload)
                    seen_names.add(path.name)
        return templates

    def find_state(
        self,
        *,
        profile_id: str | None = None,
        vendor_identity: str | None = None,
        status: str | None = None,
    ) -> ProbationTemplateState | None:
        normalized_vendor = (vendor_identity or "").strip().lower() or None
        for state in self.list_states():
            if profile_id and state.profile_id != profile_id:
                continue
            if status and state.status != status:
                continue
            if normalized_vendor:
                template = self.load_template_payload(state.template_id)
                match = template.get("match") if isinstance(template, dict) else None
                template_vendor = ""
                if isinstance(match, dict):
                    template_vendor = str(match.get("vendor_identity") or "").strip().lower()
                if template_vendor != normalized_vendor:
                    continue
            return state
        return None

    def _candidate_template_paths(self, template_id: str) -> list[Path]:
        paths = [self.build_template_path(template_id)]
        if self.legacy_templates_dir is not None:
            paths.append(self.legacy_templates_dir / f"{template_id}.json")
        return paths

    def _candidate_state_paths(self, template_id: str) -> list[Path]:
        paths = [self.build_state_path(template_id)]
        if self.legacy_state_dir is not None:
            paths.append(self.legacy_state_dir / f"{template_id}.json")
        return paths

    def _candidate_template_roots(self) -> list[Path]:
        roots = [self.templates_dir]
        if self.legacy_templates_dir is not None and self.legacy_templates_dir != self.templates_dir:
            roots.append(self.legacy_templates_dir)
        return roots

    def _candidate_state_roots(self) -> list[Path]:
        roots = [self.state_dir]
        if self.legacy_state_dir is not None and self.legacy_state_dir != self.state_dir:
            roots.append(self.legacy_state_dir)
        return roots

    def _candidate_evaluation_roots(self, template_id: str) -> list[Path]:
        roots = [self.evaluations_dir / template_id]
        if self.legacy_evaluations_dir is not None:
            roots.append(self.legacy_evaluations_dir / template_id)
        return roots

    def _candidate_shadow_roots(self, template_id: str) -> list[Path]:
        roots = [self.shadow_dir / template_id]
        if self.legacy_shadow_dir is not None:
            roots.append(self.legacy_shadow_dir / template_id)
        return roots
