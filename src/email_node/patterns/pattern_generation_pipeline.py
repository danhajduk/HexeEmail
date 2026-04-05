from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError

from email_node.patterns.pattern_generation_client import PatternGenerationClientError
from email_node.patterns.pattern_generation_request import PatternGenerationRequest
from email_node.patterns.pattern_generation_response import PatternGenerationResponse


class PatternGenerationPipelineError(RuntimeError):
    pass


class PatternGenerationPipeline:
    def __init__(self, client) -> None:
        self.client = client

    @staticmethod
    def normalize_payload(raw_payload: dict[str, object]) -> dict[str, object]:
        payload = deepcopy(raw_payload)
        if payload.get("post_process") is None:
            payload["post_process"] = {}
        if payload.get("required_fields") is None:
            payload["required_fields"] = []
        confidence_rules = payload.get("confidence_rules")
        if confidence_rules is None:
            confidence_rules = {}
            payload["confidence_rules"] = confidence_rules
        if isinstance(confidence_rules, dict) and confidence_rules.get("high_requires") is None:
            confidence_rules["high_requires"] = []
        extract = payload.get("extract")
        if isinstance(extract, dict):
            for rule in extract.values():
                if isinstance(rule, dict) and rule.get("transforms") is None:
                    rule["transforms"] = []
        return payload

    async def generate_template(self, request: PatternGenerationRequest) -> PatternGenerationResponse:
        try:
            raw_payload = await self.client.generate_pattern(request)
        except PatternGenerationClientError as exc:
            raise PatternGenerationPipelineError(str(exc)) from exc
        if not isinstance(raw_payload, dict):
            raise PatternGenerationPipelineError("Pattern generation client must return a JSON object")
        normalized = self.normalize_payload(raw_payload)
        try:
            return PatternGenerationResponse.model_validate(normalized)
        except ValidationError as exc:
            raise PatternGenerationPipelineError(f"Pattern generation response failed schema validation: {exc}") from exc
