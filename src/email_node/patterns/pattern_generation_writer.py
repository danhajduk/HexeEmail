from __future__ import annotations

import json
from pathlib import Path

from email_node.patterns.pattern_generation_response import PatternGenerationResponse


class PatternGenerationWriterError(RuntimeError):
    pass


class PatternGenerationWriter:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path(__file__).resolve().parent / "draft")

    def build_output_path(self, template_id: str) -> Path:
        return self.base_dir / f"{template_id}.json"

    def write_template(
        self,
        template: PatternGenerationResponse,
        *,
        allow_overwrite: bool = False,
    ) -> Path:
        output_path = self.build_output_path(template.template_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not allow_overwrite:
            raise PatternGenerationWriterError(f"Template file already exists: {output_path}")
        output_path.write_text(
            json.dumps(template.model_dump(mode="json"), indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        return output_path
