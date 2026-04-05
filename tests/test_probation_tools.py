from __future__ import annotations

import json
from datetime import UTC, datetime

from email_node.patterns import ProbationStore, ProbationTemplateState
from tests.test_probation_flow import build_unresolved_phase4
from scripts.probation_tools import main


def test_probation_tools_print_state(capsys, tmp_path, monkeypatch):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
        shadow_dir=tmp_path / "probation_shadow",
    )
    store.save_state(
        ProbationTemplateState(
            template_id="template-1",
            profile_id="reservation_confirmation",
            template_version="v1",
            created_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
        )
    )
    monkeypatch.setattr("scripts.probation_tools.ProbationStore", lambda: store)

    exit_code = main(["state", "template-1"])

    assert exit_code == 0
    assert '"template_id": "template-1"' in capsys.readouterr().out


def test_probation_tools_print_eligibility(capsys, tmp_path, monkeypatch):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
        shadow_dir=tmp_path / "probation_shadow",
    )
    store.save_state(
        ProbationTemplateState(
            template_id="template-1",
            profile_id="reservation_confirmation",
            template_version="v1",
            created_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 5, 22, 0, tzinfo=UTC),
            sample_count=5,
            required_field_success_rate=1.0,
            high_requires_success_rate=1.0,
        )
    )
    monkeypatch.setattr("scripts.probation_tools.ProbationStore", lambda: store)

    exit_code = main(["eligibility", "template-1"])

    assert exit_code == 0
    assert '"is_promotion_eligible": true' in capsys.readouterr().out.lower()


def test_probation_tools_run_evaluation(capsys, tmp_path, monkeypatch):
    store = ProbationStore(
        templates_dir=tmp_path / "probation",
        state_dir=tmp_path / "probation_state",
        evaluations_dir=tmp_path / "probation_evaluations",
        shadow_dir=tmp_path / "probation_shadow",
    )
    store.save_template_payload(
        "template-1",
        {
            "schema_version": "order-phase4-template.v1",
            "template_id": "template-1",
            "profile_id": "reservation_confirmation",
            "template_version": "v1",
            "enabled": True,
            "match": {"vendor_identity": "recreation_gov"},
            "extract": {
                "order_number": {"method": "regex", "pattern": r"(?m)^([0-9]{10})$"},
            },
            "required_fields": ["order_number"],
            "confidence_rules": {"high_requires": ["order_number"]},
            "post_process": {},
        },
    )
    monkeypatch.setattr("scripts.probation_tools.ProbationStore", lambda: store)

    phase4 = build_unresolved_phase4()
    phase3_path = tmp_path / "phase3.json"
    phase3_path.write_text(json.dumps(phase4.phase3_reference.model_dump(mode="json")), encoding="utf-8")

    exit_code = main(["evaluate", "template-1", str(phase3_path)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"template_id": "template-1"' in output
    assert '"required_fields_present": true' in output
