from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx

from email_node.patterns.pattern_generation_request import PatternGenerationRequest
from logging_utils import get_logger


class PatternGenerationClientError(RuntimeError):
    pass


class PatternGenerationParseError(PatternGenerationClientError):
    pass


LOGGER = get_logger(__name__)


class PatternGenerationClient:
    PROMPT_ID = "prompt.email.order_pattern_template_creation"

    def __init__(
        self,
        *,
        target_api_base_url: str,
        prompt_definition_path: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
        debug_full_response: bool = False,
    ) -> None:
        self.target_api_base_url = target_api_base_url.rstrip("/")
        self.prompt_definition_path = prompt_definition_path or (
            Path(__file__).resolve().parents[3] / "runtime" / "prompts" / f"{self.PROMPT_ID}.json"
        )
        self.transport = transport
        self.timeout = timeout
        self.debug_full_response = debug_full_response

    def load_prompt_definition(self) -> dict[str, object]:
        try:
            payload = json.loads(self.prompt_definition_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise PatternGenerationClientError(f"Prompt definition file not found: {self.prompt_definition_path}") from exc
        if not isinstance(payload, dict):
            raise PatternGenerationClientError("Prompt definition must be a JSON object")
        if payload.get("prompt_id") != self.PROMPT_ID:
            raise PatternGenerationClientError(f"Prompt definition prompt_id mismatch: {payload.get('prompt_id')}")
        return payload

    @staticmethod
    def _extract_json_schema(prompt_definition: dict[str, object]) -> dict[str, object]:
        runtime = prompt_definition.get("node_runtime")
        if not isinstance(runtime, dict):
            raise PatternGenerationClientError("Prompt definition is missing node_runtime")
        json_schema = runtime.get("json_schema")
        if not isinstance(json_schema, dict):
            raise PatternGenerationClientError("Prompt definition is missing node_runtime.json_schema")
        return json_schema

    def build_request_body(self, request: PatternGenerationRequest) -> dict[str, object]:
        prompt_definition = self.load_prompt_definition()
        prompt_runtime = prompt_definition.get("node_runtime")
        if not isinstance(prompt_runtime, dict):
            raise PatternGenerationClientError("Prompt definition is missing node_runtime")
        return {
            "task_id": f"pattern-generation-{uuid.uuid4().hex}",
            "prompt_id": str(prompt_definition["prompt_id"]),
            "prompt_version": str(prompt_definition["version"]),
            "task_family": str(prompt_definition.get("task_family") or "task.structured_extraction"),
            "requested_by": "node-email",
            "service_id": str(prompt_definition.get("service_id") or "node-email"),
            "customer_id": "local-user",
            "trace_id": f"trace-pattern-{uuid.uuid4().hex}",
            "inputs": {
                **request.model_dump(mode="json"),
                "json_schema": self._extract_json_schema(prompt_definition),
            },
            "timeout_s": int(prompt_runtime.get("timeout_s", 45)),
        }

    @staticmethod
    def _parse_json_only_output(raw_output: object) -> dict[str, object]:
        if isinstance(raw_output, dict):
            return raw_output
        if not isinstance(raw_output, str):
            raise PatternGenerationParseError("AI response output must be a JSON object or JSON string")
        stripped = raw_output.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            raise PatternGenerationParseError("AI response must be JSON only without markdown or text wrapping")
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PatternGenerationParseError(f"AI response did not contain valid JSON: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise PatternGenerationParseError("AI response JSON must decode to an object")
        return parsed

    async def _execute_once(self, request_body: dict[str, object]) -> dict[str, object]:
        safe_inputs = request_body.get("inputs", {})
        LOGGER.info(
            "Pattern generation request started",
            extra={
                "event_data": {
                    "target_api_base_url": self.target_api_base_url,
                    "prompt_id": request_body.get("prompt_id"),
                    "task_id": request_body.get("task_id"),
                    "template_id": safe_inputs.get("template_id") if isinstance(safe_inputs, dict) else None,
                    "profile_id": safe_inputs.get("profile_id") if isinstance(safe_inputs, dict) else None,
                    "vendor_identity": safe_inputs.get("vendor_identity") if isinstance(safe_inputs, dict) else None,
                    "expected_label": safe_inputs.get("expected_label") if isinstance(safe_inputs, dict) else None,
                    "from_email": safe_inputs.get("from_email") if isinstance(safe_inputs, dict) else None,
                }
            },
        )
        async with httpx.AsyncClient(
            base_url=self.target_api_base_url,
            transport=self.transport,
            timeout=self.timeout,
        ) as client:
            response = await client.post("/api/execution/direct", json=request_body)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise PatternGenerationClientError("AI execution response must be a JSON object")
        output = payload.get("output")
        output_preview = output if self.debug_full_response else str(output)[:500]
        LOGGER.info(
            "Pattern generation raw AI response received",
            extra={
                "event_data": {
                    "task_id": request_body.get("task_id"),
                    "status": payload.get("status"),
                    "output_preview": output_preview,
                    "debug_full_response": self.debug_full_response,
                }
            },
        )
        return self._parse_json_only_output(output)

    async def generate_pattern(self, request: PatternGenerationRequest) -> dict[str, object]:
        request_body = self.build_request_body(request)
        try:
            return await self._execute_once(request_body)
        except PatternGenerationParseError:
            return await self._execute_once(request_body)
