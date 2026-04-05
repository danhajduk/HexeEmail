from __future__ import annotations

from typing import Any

import httpx


class AiNodeGateway:
    def __init__(self, service: Any) -> None:
        self.service = service

    def assert_enabled(self) -> None:
        if not self.service.runtime.runtime_ai_calls_enabled():
            raise ValueError(self.service.runtime.runtime_ai_disabled_message())

    def normalize_target_api_base_url(self, target_api_base_url: str | None) -> str:
        return self.service.runtime.normalize_target_api_base_url(target_api_base_url)

    async def list_prompt_services(self, target_api_base_url: str) -> list[dict[str, object]]:
        self.assert_enabled()
        async with httpx.AsyncClient(
            base_url=target_api_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            response = await client.get("/api/prompts/services")
            response.raise_for_status()
            payload = response.json()
        state = payload.get("state") if isinstance(payload, dict) else None
        prompt_services = state.get("prompt_services") if isinstance(state, dict) else None
        return prompt_services if isinstance(prompt_services, list) else []

    async def get_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
    ) -> dict[str, object] | None:
        self.assert_enabled()
        async with httpx.AsyncClient(
            base_url=target_api_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            response = await client.get(f"/api/prompts/services/{prompt_id}")
            if response.status_code == 400:
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                detail = payload.get("detail") if isinstance(payload, dict) else None
                if detail == "prompt_id is not registered":
                    return None
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or not payload.get("configured"):
            return None
        prompt = payload.get("prompt")
        return prompt if isinstance(prompt, dict) else None

    async def register_prompt_service(
        self,
        target_api_base_url: str,
        request_body: dict[str, object],
    ) -> dict[str, object]:
        self.assert_enabled()
        async with httpx.AsyncClient(
            base_url=target_api_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            registration_response = await client.post("/api/prompts/services", json=request_body)
            registration_response.raise_for_status()
            return registration_response.json()

    async def update_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
        request_body: dict[str, object],
    ) -> dict[str, object]:
        self.assert_enabled()
        async with httpx.AsyncClient(
            base_url=target_api_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            update_response = await client.put(f"/api/prompts/services/{prompt_id}", json=request_body)
            update_response.raise_for_status()
            return update_response.json()

    async def retire_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
        reason: str,
    ) -> dict[str, object]:
        self.assert_enabled()
        payload = {"state": "retired", "reason": reason}
        async with httpx.AsyncClient(
            base_url=target_api_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            lifecycle_response = await client.post(f"/api/prompts/services/{prompt_id}/lifecycle", json=payload)
            lifecycle_response.raise_for_status()
            return lifecycle_response.json()

    async def review_prompt_service(
        self,
        target_api_base_url: str,
        *,
        prompt_id: str,
        review_status: str,
        reason: str | None,
    ) -> dict[str, object]:
        self.assert_enabled()
        payload = {"review_status": review_status, "reason": reason}
        async with httpx.AsyncClient(
            base_url=target_api_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            review_response = await client.post(f"/api/prompts/services/{prompt_id}/review", json=payload)
            review_response.raise_for_status()
            return review_response.json()

    async def migrate_prompts_to_review_due(self, target_api_base_url: str) -> dict[str, object]:
        self.assert_enabled()
        async with httpx.AsyncClient(
            base_url=target_api_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            migration_response = await client.post("/api/prompts/services/migrations/review-due")
            migration_response.raise_for_status()
            return migration_response.json()

    async def execute_direct(
        self,
        target_api_base_url: str | None,
        *,
        request_body: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        self.assert_enabled()
        normalized_target_base_url = self.normalize_target_api_base_url(target_api_base_url)
        async with httpx.AsyncClient(
            base_url=normalized_target_base_url,
            timeout=self.service.core_client.timeout,
            transport=self.service.core_client.transport,
        ) as client:
            execution_response = await client.post("/api/execution/direct", json=request_body)
            execution_response.raise_for_status()
            payload = execution_response.json()
        return normalized_target_base_url, payload if isinstance(payload, dict) else {}
