from __future__ import annotations

from email_node.patterns.pattern_generation_pipeline import PatternGenerationPipelineError
from email_node.patterns.pattern_generation_request import PatternGenerationRequest
from email_node.patterns.pattern_generation_writer import PatternGenerationWriterError


class PatternGenerationServiceError(RuntimeError):
    pass


class PatternGenerationService:
    def __init__(self, pipeline, writer) -> None:
        self.pipeline = pipeline
        self.writer = writer

    async def generate(
        self,
        request: PatternGenerationRequest,
        *,
        allow_overwrite: bool = False,
    ) -> dict[str, object]:
        try:
            template = await self.pipeline.generate_template(request)
            output_path = self.writer.write_template(template, allow_overwrite=allow_overwrite)
        except (PatternGenerationPipelineError, PatternGenerationWriterError) as exc:
            raise PatternGenerationServiceError(str(exc)) from exc
        return {
            "ok": True,
            "template_id": template.template_id,
            "file_path": str(output_path),
        }
