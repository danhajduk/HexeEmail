from __future__ import annotations

from typing import Any

from core.capability_client import CapabilityDeclarationResult
from core.governance_client import GovernanceSnapshot
from logging_utils import get_logger


LOGGER = get_logger(__name__)


class GovernanceManager:
    def __init__(self, service: Any) -> None:
        self.service = service

    def capability_setup_summary(self, provider_overview: dict[str, object]) -> dict[str, object]:
        provider_summaries = provider_overview.get("providers") if isinstance(provider_overview, dict) else {}
        connected_providers = [
            provider_id
            for provider_id, summary in (provider_summaries.items() if isinstance(provider_summaries, dict) else [])
            if isinstance(summary, dict) and summary.get("provider_state") == "connected"
        ]
        selected_capabilities = self.service.selected_task_capabilities()
        trust_valid = self.service.state.trust_state == "trusted"
        node_identity_valid = bool(self.service.effective_node_name())
        provider_selection_valid = bool(connected_providers)
        task_capability_selection_valid = bool(selected_capabilities)
        core_runtime_context_valid = bool(self.service.effective_core_base_url() and self.service.state.node_id)
        blocking_reasons: list[str] = []
        if not trust_valid:
            blocking_reasons.append("trust not active")
        if not node_identity_valid:
            blocking_reasons.append("node identity is incomplete")
        if not provider_selection_valid:
            blocking_reasons.append("connect Gmail before declaring capabilities")
        if not task_capability_selection_valid:
            blocking_reasons.append("select at least one task capability")
        if not core_runtime_context_valid:
            blocking_reasons.append("core runtime context is not ready")

        return {
            "readiness_flags": {
                "trust_state_valid": trust_valid,
                "node_identity_valid": node_identity_valid,
                "provider_selection_valid": provider_selection_valid,
                "task_capability_selection_valid": task_capability_selection_valid,
                "core_runtime_context_valid": core_runtime_context_valid,
            },
            "provider_selection": {
                "configured": provider_selection_valid,
                "enabled_count": len(connected_providers),
                "enabled": connected_providers,
                "supported": {
                    "cloud": list(provider_overview.get("supported_providers") or []),
                    "local": [],
                    "future": [],
                },
            },
            "task_capability_selection": {
                "configured": task_capability_selection_valid,
                "selected_count": len(selected_capabilities),
                "selected": selected_capabilities,
                "available": list(self.service.available_task_capabilities),
            },
            "blocking_reasons": blocking_reasons,
            "declaration_allowed": not blocking_reasons,
        }

    async def refresh_post_trust_state(self) -> None:
        if (
            self.service.state.trust_state != "trusted"
            or not self.service.state.node_id
            or not self.service.effective_core_base_url()
        ):
            return
        provider_overview = await self.service.providers.provider_status_snapshot_async()
        capability_setup = self.capability_setup_summary(provider_overview)
        connected_providers = capability_setup.get("provider_selection", {}).get("enabled", [])
        self.service.state.enabled_providers = list(connected_providers) if isinstance(connected_providers, list) else []
        self.service.state_store.save(self.service.state)
        await self.update_operational_readiness()

    async def declare_selected_capabilities(self):
        if (
            self.service.state.trust_state != "trusted"
            or not self.service.state.node_id
            or not self.service.effective_core_base_url()
        ):
            raise ValueError("trusted node context is required before declaring capabilities")
        provider_overview = await self.service.providers.provider_status_snapshot_async()
        capability_setup = self.capability_setup_summary(provider_overview)
        connected_providers = capability_setup.get("provider_selection", {}).get("enabled", [])
        self.service.state.enabled_providers = list(connected_providers) if isinstance(connected_providers, list) else []
        if not capability_setup.get("declaration_allowed"):
            self.service.state.capability_declaration_status = "pending"
            self.service.state.governance_sync_status = "pending"
            self.service.state.active_governance_version = None
            self.service.state_store.save(self.service.state)
            await self.update_operational_readiness()
            raise ValueError("capability declaration is not ready yet")
        await self.declare_capabilities(provider_overview)
        await self.sync_governance()
        await self.update_operational_readiness()
        return await self.service.status()

    async def redeclare_capabilities(self, *, force: bool = False):
        if force:
            self.service.state.capability_declaration_status = "pending"
            self.service.state_store.save(self.service.state)
        return await self.declare_selected_capabilities()

    async def rebuild_capabilities(self, *, force: bool = False) -> dict[str, object]:
        if force:
            self.service.state.capability_declaration_status = "pending"
            self.service.state.governance_sync_status = "pending"
            self.service.state.active_governance_version = None
            self.service.state_store.save(self.service.state)
        await self.refresh_post_trust_state()
        resolved = await self.service.resolved_node_capabilities()
        return {"status": "rebuilt", "force_refresh": force, "resolved": resolved}

    async def declare_capabilities(self, overview: dict[str, object] | None = None) -> CapabilityDeclarationResult:
        overview = overview or await self.service.providers.provider_status_snapshot_async()
        enabled_providers: list[str] = []
        for provider_id, provider_summary in overview["providers"].items():
            if isinstance(provider_summary, dict) and provider_summary.get("provider_state") == "connected":
                enabled_providers.append(provider_id)
        manifest = self.service.capability_manifest_builder.build(
            node_id=self.service.state.node_id or "",
            node_type=self.service.config.node_type,
            node_name=self.service.effective_node_name() or "",
            node_software_version=self.service.config.node_software_version,
            declared_task_families=self.service.selected_task_capabilities(),
            supported_providers=list(overview["supported_providers"]),
            enabled_providers=enabled_providers,
        )
        result = await self.service.capability_client.declare(
            self.service.effective_core_base_url() or "",
            manifest,
            trust_token=(self.service.trust_material.node_trust_token if self.service.trust_material is not None else ""),
        )
        self.service.state.capability_declaration_status = "accepted" if result.accepted else "rejected"
        self.service.state.capability_declared_at = result.submitted_at
        self.service.state.enabled_providers = enabled_providers
        self.service.state_store.save(self.service.state)
        LOGGER.info(
            "Capability declaration submitted",
            extra={
                "event_data": {
                    "accepted": result.accepted,
                    "supported_providers": manifest.supported_providers,
                    "enabled_providers": manifest.enabled_providers,
                }
            },
        )
        return result

    async def sync_governance(self) -> GovernanceSnapshot:
        if self.service.trust_material is None:
            snapshot = GovernanceSnapshot(
                node_id=self.service.state.node_id or "",
                present=False,
                last_sync_result="trust_material_missing",
            )
            self.service.state.governance_sync_status = snapshot.last_sync_result
            self.service.state.governance_synced_at = snapshot.synced_at
            self.service.state.active_governance_version = None
            self.service.state_store.save(self.service.state)
            return snapshot
        snapshot = await self.service.governance_client.fetch(
            self.service.effective_core_base_url() or "",
            self.service.state.node_id or "",
            trust_token=self.service.trust_material.node_trust_token,
            current_governance_version=self.service.state.active_governance_version,
        )
        self.service.state.governance_sync_status = snapshot.last_sync_result
        self.service.state.governance_synced_at = snapshot.synced_at
        self.service.state.active_governance_version = snapshot.governance_version
        self.service.state_store.save(self.service.state)
        LOGGER.info(
            "Governance sync result",
            extra={
                "event_data": {
                    "present": snapshot.present,
                    "last_sync_result": snapshot.last_sync_result,
                    "governance_version": snapshot.governance_version,
                }
            },
        )
        return snapshot

    async def update_operational_readiness(self) -> None:
        gmail_state = await self.service.provider_registry.get_provider("gmail").get_provider_state()
        self.service.state.operational_readiness = self.service.readiness_evaluator.evaluate(
            trust_state=self.service.state.trust_state,
            capability_declaration_status=self.service.state.capability_declaration_status,
            governance_sync_status=self.service.state.governance_sync_status,
            gmail_provider_state=gmail_state,
        )
        self.service.state_store.save(self.service.state)
