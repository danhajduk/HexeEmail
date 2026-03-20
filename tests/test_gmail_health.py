from __future__ import annotations

from providers.gmail.health import GmailHealthEvaluator
from providers.gmail.models import GmailOAuthConfig, GmailTokenRecord
from providers.models import ProviderAccountRecord, ProviderId


def build_config() -> GmailOAuthConfig:
    return GmailOAuthConfig(
        enabled=True,
        client_id="client-id",
        client_secret_ref="env:GMAIL_CLIENT_SECRET",
        redirect_uri="http://127.0.0.1:9002/providers/gmail/oauth/callback",
    )


def test_gmail_health_reports_connected_when_identity_and_refresh_are_present():
    evaluator = GmailHealthEvaluator()
    health = evaluator.evaluate(
        build_config(),
        account_id="primary",
        token_record=GmailTokenRecord(
            account_id="primary",
            access_token="access-token",
            refresh_token="refresh-token",
            granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
        ),
        account_record=ProviderAccountRecord(
            provider_id=ProviderId.GMAIL,
            account_id="primary",
            status="token_exchanged",
            email_address="primary@example.com",
        ),
    )

    assert health.status == "connected"


def test_gmail_health_reports_oauth_pending_when_token_missing():
    evaluator = GmailHealthEvaluator()
    health = evaluator.evaluate(build_config(), account_id="primary", token_record=None, account_record=None)

    assert health.status == "oauth_pending"


def test_gmail_health_reports_degraded_when_refresh_or_identity_missing():
    evaluator = GmailHealthEvaluator()
    health = evaluator.evaluate(
        build_config(),
        account_id="primary",
        token_record=GmailTokenRecord(
            account_id="primary",
            access_token="access-token",
            granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
        ),
        account_record=None,
    )

    assert health.status == "degraded"


def test_gmail_health_reports_revoked_from_account_record():
    evaluator = GmailHealthEvaluator()
    health = evaluator.evaluate(
        build_config(),
        account_id="primary",
        token_record=GmailTokenRecord(
            account_id="primary",
            access_token="access-token",
            refresh_token="refresh-token",
            granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
        ),
        account_record=ProviderAccountRecord(
            provider_id=ProviderId.GMAIL,
            account_id="primary",
            status="revoked",
        ),
    )

    assert health.status == "revoked"


def test_gmail_health_reports_invalid_config_when_required_fields_missing():
    evaluator = GmailHealthEvaluator()
    health = evaluator.evaluate(GmailOAuthConfig(enabled=True), account_id="primary", token_record=None, account_record=None)

    assert health.status == "invalid_config"
