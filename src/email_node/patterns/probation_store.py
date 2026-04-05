from __future__ import annotations

import json
from pathlib import Path

from email_node.patterns.probation_state import ProbationTemplateState


class ProbationStore:
    def __init__(
        self,
        *,
        templates_dir: Path | None = None,
        state_dir: Path | None = None,
        evaluations_dir: Path | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        self.templates_dir = templates_dir or (base_dir / "probation")
        self.state_dir = state_dir or (base_dir / "probation_state")
        self.evaluations_dir = evaluations_dir or (base_dir / "probation_evaluations")
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)

    def build_template_path(self, template_id: str) -> Path:
        return self.templates_dir / f"{template_id}.json"

    def build_state_path(self, template_id: str) -> Path:
        return self.state_dir / f"{template_id}.json"

    def build_evaluation_path(self, template_id: str, message_id: str) -> Path:
        return self.evaluations_dir / template_id / f"{message_id}.json"

    def save_template_payload(self, template_id: str, payload: dict[str, object]) -> Path:
        path = self.build_template_path(template_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return path

    def load_template_payload(self, template_id: str) -> dict[str, object] | None:
        path = self.build_template_path(template_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def save_state(self, state: ProbationTemplateState) -> Path:
        path = self.build_state_path(state.template_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_state(self, template_id: str) -> ProbationTemplateState | None:
        path = self.build_state_path(template_id)
        if not path.exists():
            return None
        return ProbationTemplateState.model_validate_json(path.read_text(encoding="utf-8"))

    def save_evaluation(self, evaluation) -> Path:
        path = self.build_evaluation_path(evaluation.template_id, evaluation.message_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(evaluation, "model_dump_json"):
            path.write_text(evaluation.model_dump_json(indent=2), encoding="utf-8")
        else:
            path.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
        return path

    def list_evaluations(self, template_id: str) -> list[dict[str, object]]:
        root = self.evaluations_dir / template_id
        if not root.exists():
            return []
        evaluations: list[dict[str, object]] = []
        for path in sorted(root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                evaluations.append(payload)
        return evaluations

    def list_states(self) -> list[ProbationTemplateState]:
        states: list[ProbationTemplateState] = []
        for path in sorted(self.state_dir.glob("*.json")):
            states.append(ProbationTemplateState.model_validate_json(path.read_text(encoding="utf-8")))
        return states

    def list_templates(self) -> list[dict[str, object]]:
        templates: list[dict[str, object]] = []
        for path in sorted(self.templates_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload["_path"] = str(path)
                templates.append(payload)
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
