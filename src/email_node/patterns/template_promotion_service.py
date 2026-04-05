from __future__ import annotations

import shutil
from pathlib import Path

from email_node.patterns.probation_store import ProbationStore


class TemplatePromotionServiceError(RuntimeError):
    pass


class TemplatePromotionService:
    def __init__(
        self,
        *,
        probation_store: ProbationStore,
        active_dir: Path | None = None,
    ) -> None:
        self.probation_store = probation_store
        self.active_dir = active_dir or (Path(__file__).resolve().parents[3] / "runtime" / "order_templates")

    def promote(self, template_id: str) -> Path:
        source_path = self.probation_store.build_template_path(template_id)
        if not source_path.exists():
            raise TemplatePromotionServiceError(f"Probation template not found: {template_id}")
        target_path = self.active_dir / source_path.name
        self.active_dir.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            raise TemplatePromotionServiceError(f"Active template already exists: {target_path}")
        shutil.copy2(source_path, target_path)
        return target_path
