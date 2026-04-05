from __future__ import annotations

from datetime import UTC, datetime

from email_node.patterns import ProbationStore, ProbationTemplateState


def build_state() -> ProbationTemplateState:
    now = datetime(2026, 4, 5, 22, 0, tzinfo=UTC)
    return ProbationTemplateState(
        template_id="recreation_gov_reservation_confirmation.v1",
        profile_id="reservation_confirmation",
        template_version="v1",
        created_at=now,
        updated_at=now,
    )


def test_probation_state_defaults_initialize_correctly():
    state = build_state()

    assert state.status == "probation"
    assert state.sample_count == 1
    assert state.success_count == 0
    assert state.failure_count == 0
    assert state.hard_failure_count == 0


def test_probation_store_persists_template_and_state(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
    )
    state = build_state()
    store.save_template_payload(
        state.template_id,
        {
            "template_id": state.template_id,
            "profile_id": state.profile_id,
            "template_version": state.template_version,
            "match": {"vendor_identity": "recreation_gov"},
        },
    )
    store.save_state(state)

    loaded_state = store.load_state(state.template_id)
    loaded_template = store.load_template_payload(state.template_id)

    assert loaded_state is not None
    assert loaded_state.template_id == state.template_id
    assert loaded_template is not None
    assert loaded_template["profile_id"] == "reservation_confirmation"


def test_probation_store_can_find_existing_probation_by_profile_and_vendor(tmp_path):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
    )
    state = build_state()
    store.save_template_payload(
        state.template_id,
        {
            "template_id": state.template_id,
            "profile_id": state.profile_id,
            "template_version": state.template_version,
            "match": {"vendor_identity": "recreation_gov"},
        },
    )
    store.save_state(state)

    found = store.find_state(
        profile_id="reservation_confirmation",
        vendor_identity="recreation_gov",
        status="probation",
    )

    assert found is not None
    assert found.template_id == state.template_id
