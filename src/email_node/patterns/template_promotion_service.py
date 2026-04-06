from __future__ import annotations

import shutil
from pathlib import Path

from email_node.patterns.probation_store import ProbationStore
from email_node.shared_pipeline_core.families import get_flow_family_config
from logging_utils import get_logger


class TemplatePromotionServiceError(RuntimeError):
    pass


LOGGER = get_logger(__name__)


class TemplatePromotionService:
    def __init__(
        self,
        *,
        probation_store: ProbationStore,
        active_dir: Path | None = None,
    ) -> None:
        self.probation_store = probation_store
        self.active_dir = active_dir or get_flow_family_config("order").template_dir

    def promote(self, template_id: str) -> Path:
        source_path = self.probation_store.build_template_path(template_id)
        if not source_path.exists():
            raise TemplatePromotionServiceError(f"Probation template not found: {template_id}")
        target_path = self.active_dir / source_path.name
        self.active_dir.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            raise TemplatePromotionServiceError(f"Active template already exists: {target_path}")
        shutil.copy2(source_path, target_path)
        LOGGER.info(
            "Probation template promoted to active",
            extra={"event_data": {"template_id": template_id, "target_path": str(target_path)}},
        )
        return target_path
