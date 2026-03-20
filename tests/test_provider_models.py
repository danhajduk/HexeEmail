from __future__ import annotations

from providers.models import (
    ProviderAccountRecord,
    ProviderActivationSummary,
    ProviderHealth,
    ProviderId,
    ProviderValidationResult,
)


def test_provider_validation_result_captures_missing_and_invalid_fields():
    result = ProviderValidationResult(
        ok=False,
        missing_fields=["client_id"],
        invalid_fields=["redirect_uri"],
        messages=["redirect_uri must be https"],
    )

    assert result.ok is False
    assert result.missing_fields == ["client_id"]
    assert result.invalid_fields == ["redirect_uri"]


def test_provider_account_record_defaults_to_provider_neutral_pending_state():
    record = ProviderAccountRecord(
        provider_id=ProviderId.GMAIL,
        account_id="primary",
    )

    assert record.status == "not_configured"
    assert record.email_address is None
    assert record.external_account_id is None


def test_provider_activation_summary_can_hold_health_and_accounts():
    summary = ProviderActivationSummary(
        provider_id=ProviderId.GMAIL,
        supported=True,
        enabled=True,
        configured=True,
        provider_state="configured",
        health=ProviderHealth(
            provider_id=ProviderId.GMAIL,
            status="oauth_pending",
            detail="Operator approval still required.",
        ),
        accounts=[
            ProviderAccountRecord(
                provider_id=ProviderId.GMAIL,
                account_id="primary",
                status="oauth_pending",
            )
        ],
    )

    assert summary.provider_state == "configured"
    assert summary.health is not None
    assert summary.health.status == "oauth_pending"
    assert summary.accounts[0].status == "oauth_pending"
