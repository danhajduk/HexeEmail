from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class SharedEmailPipelineHooks:
    scrub: Callable[[object], object]
    detect_profile: Callable[[object], object]
    extract_template: Callable[[object], object]
    attach_probation_template: Callable[[object], Awaitable[object]]
    run_probation_shadow_mode: Callable[[object], object]
    decide: Callable[[object], object]
    persist: Callable[[object, object], object]
    authorize_actions: Callable[[object, object], object]
    route_actions: Callable[[object, object, object], object]
    write_order_record: Callable[[object, object, object], object]
    build_user_notification: Callable[[object, object, object], object]
    build_tracking_monitor: Callable[[object, object, object], object]


class SharedEmailPipelineCore:
    def __init__(self, *, flow_family: str, hooks: SharedEmailPipelineHooks) -> None:
        self.flow_family = flow_family
        self.hooks = hooks

    async def process_normalized_email(self, normalized: object) -> dict[str, object]:
        phase2 = self.hooks.scrub(normalized)
        phase3 = self.hooks.detect_profile(phase2)
        phase4 = self.hooks.extract_template(phase3)
        phase4 = await self.hooks.attach_probation_template(phase4)
        phase4 = self.hooks.run_probation_shadow_mode(phase4)
        phase6 = self.hooks.decide(phase4)
        phase7 = self.hooks.persist(phase6, phase4)
        action_gate = self.hooks.authorize_actions(phase6, phase4)
        action_router = self.hooks.route_actions(phase6, action_gate, phase4)
        order_record_write = self.hooks.write_order_record(phase6, phase4, action_router)
        user_notification = self.hooks.build_user_notification(phase6, action_router, phase4)
        tracking_monitor = self.hooks.build_tracking_monitor(phase6, action_router, phase4)
        phase7_result = {
            "flow_family": self.flow_family,
            "persisted_result": phase7.persisted,
            "persistence_reason": phase7.blocked_reason or phase7.trust_level,
            "actions_allowed": action_gate.actions_allowed,
            "action_intents": list(action_router.action_intents),
            "action_results": {
                "order_record_write": order_record_write.model_dump(mode="json"),
                "user_notification": user_notification.model_dump(mode="json"),
                "tracking_monitor": tracking_monitor.model_dump(mode="json"),
            },
        }
        return {
            "flow_family": self.flow_family,
            "phase2": phase2,
            "phase3": phase3,
            "phase4": phase4,
            "phase6": phase6,
            "phase7": phase7,
            "action_gate": action_gate,
            "action_router": action_router,
            "order_record_write": order_record_write,
            "user_notification": user_notification,
            "tracking_monitor": tracking_monitor,
            "phase7_result": phase7_result,
        }
