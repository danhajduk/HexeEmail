from __future__ import annotations

from scripts.update_order_flow_tests import update_doc_entry


def test_update_doc_entry_replaces_only_phase2_block():
    original = (
        "19abc | Subject\n\n"
        "Phase 1 output:\n"
        "{phase1-old}\n\n"
        "Phase 2 output:\n"
        "{phase2-old}\n\n"
        "Phase 3 output:\n"
        "{phase3-old}\n\n"
        "Phase 4 output:\n"
        "{phase4-old}\n"
    )

    updated = update_doc_entry(
        original,
        message_id="19abc",
        subject="Subject",
        phase1_json="{phase1-new}",
        phase2_json="{phase2-new}",
        phase3_json="{phase3-new}",
        phase4_json="{phase4-new}",
    )

    assert "{phase1-old}" in updated
    assert "{phase1-new}" not in updated
    assert "{phase2-old}" in updated
    assert "{phase2-new}" not in updated
    assert "{phase3-old}" in updated
    assert "{phase3-new}" not in updated
    assert "{phase4-new}" in updated
    assert "{phase4-old}" not in updated


def test_update_doc_entry_appends_missing_entry():
    original = "mail list:\n19abc | Subject\n"

    updated = update_doc_entry(
        original,
        message_id="19def",
        subject="Other Subject",
        phase1_json="{phase1}",
        phase2_json="{phase2}",
        phase3_json="{phase3}",
        phase4_json="{phase4}",
    )

    assert "19def | Other Subject" in updated
    assert "Phase 1 output:\n{phase1}" in updated
    assert "Phase 2 output:\n{phase2}" in updated
    assert "Phase 3 output:\n{phase3}" in updated
    assert "Phase 4 output:\n{phase4}" in updated


def test_update_doc_entry_replaces_phase2_block_with_backslashes():
    original = (
        "19abc | Subject\n\n"
        "Phase 1 output:\n"
        "{phase1-old}\n\n"
        "Phase 2 output:\n"
        "{\"url\": \"https://example.com/old\"}\n\n"
        "Phase 3 output:\n"
        "{\"profile\": \"old\"}\n\n"
        "Phase 4 output:\n"
        "{\"fields\": {\"old\": true}}\n"
    )

    updated = update_doc_entry(
        original,
        message_id="19abc",
        subject="Subject",
        phase1_json="{phase1-new}",
        phase2_json="{\"url\": \"https://example.com/new\\\\u1234\"}",
        phase3_json="{\"profile\": \"new\"}",
        phase4_json="{\"fields\": {\"new\": true}}",
    )

    assert "{\"fields\": {\"new\": true}}" in updated


def test_update_doc_entry_appends_phase4_without_touching_phase2_or_phase3():
    original = (
        "19abc | Subject\n\n"
        "Phase 1 output:\n"
        "{phase1-old}\n\n"
        "Phase 2 output:\n"
        "{phase2-old}\n\n"
        "Phase 3 output:\n"
        "{phase3-old}\n"
    )

    updated = update_doc_entry(
        original,
        message_id="19abc",
        subject="Subject",
        phase1_json="{phase1-new}",
        phase2_json="{phase2-new}",
        phase3_json="{phase3-new}",
        phase4_json="{phase4-new}",
    )

    assert "{phase1-old}" in updated
    assert "{phase2-old}" in updated
    assert "{phase3-old}" in updated
    assert "{phase2-new}" not in updated
    assert "{phase3-new}" not in updated
    assert "Phase 4 output:\n{phase4-new}" in updated
