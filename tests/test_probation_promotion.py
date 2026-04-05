from __future__ import annotations

import json
from datetime import UTC, datetime

from email_node.patterns import (
    ProbationPromotionManager,
    ProbationPromotionPolicy,
    ProbationTemplateState,
    ProbationStore,
    TemplatePromotionService,
)


def build_state(**updates) -> ProbationTemplateState:
    payload = {
        "template_id": "recreation_gov_reservation_confirmation.v1",
        "profile_id": "reservation_confirmation",
        "template_version": "v1",
        "created_at": datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
        "sample_count": 5,
        "success_count": 5,
        "failure_count": 0,
        "hard_failure_count": 0,
        "required_field_success_rate": 1.0,
        "high_requires_success_rate": 1.0,
    }
    payload.update(updates)
    return ProbationTemplateState(**payload)


def test_probation_policy_reports_eligibility_thresholds():
    policy = ProbationPromotionPolicy()

    assert policy.is_promotion_eligible(build_state()) is True
    assert policy.should_mark_for_refinement(build_state(required_field_success_rate=0.7)) is True
    assert policy.should_reject_template(build_state(hard_failure_count=3, success_count=1, failure_count=4)) is True


def test_template_promotion_service_copies_probation_template_to_active_dir(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
    )
    active_dir = tmp_path / "active"
    template_id = "recreation_gov_reservation_confirmation.v1"
    store.save_template_payload(
        template_id,
        {
            "template_id": template_id,
            "profile_id": "reservation_confirmation",
            "template_version": "v1",
            "match": {"vendor_identity": "recreation_gov"},
        },
    )

    path = TemplatePromotionService(probation_store=store, active_dir=active_dir).promote(template_id)

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["template_id"] == template_id


def test_probation_promotion_manager_marks_template_active_when_eligible(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
    )
    active_dir = tmp_path / "active"
    template_id = "recreation_gov_reservation_confirmation.v1"
    store.save_template_payload(
        template_id,
        {
            "template_id": template_id,
            "profile_id": "reservation_confirmation",
            "template_version": "v1",
            "match": {"vendor_identity": "recreation_gov"},
        },
    )

    manager = ProbationPromotionManager(
        promotion_service=TemplatePromotionService(probation_store=store, active_dir=active_dir),
        policy=ProbationPromotionPolicy(),
    )
    updated = manager.evaluate_and_apply(build_state())

    assert updated.status == "active"
    assert updated.promotion_eligible is True
    assert (active_dir / f"{template_id}.json").exists()
