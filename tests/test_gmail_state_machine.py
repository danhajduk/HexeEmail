from __future__ import annotations

import pytest

from providers.gmail.account_store import GmailAccountStore
from providers.gmail.state_machine import GmailAccountStateMachine, ProviderAccountStateError


def test_gmail_state_machine_enforces_valid_transitions(tmp_path):
    machine = GmailAccountStateMachine(GmailAccountStore(tmp_path))

    record = machine.ensure_account("primary")
    assert record.status == "not_configured"

    record = machine.transition("primary", "oauth_pending")
    assert record.status == "oauth_pending"

    record = machine.transition("primary", "token_exchanged")
    assert record.status == "token_exchanged"

    record = machine.transition("primary", "connected")
    assert record.status == "connected"


def test_gmail_state_machine_rejects_invalid_transition(tmp_path):
    machine = GmailAccountStateMachine(GmailAccountStore(tmp_path))
    machine.ensure_account("primary")

    with pytest.raises(ProviderAccountStateError):
        machine.transition("primary", "connected")
