from __future__ import annotations

from email.utils import parseaddr

from providers.gmail.models import (
    GmailFullHtmlExtractionRule,
    GmailLabelOverrideRule,
    GmailRuleMatchType,
    GmailStoredMessage,
)


GMAIL_RULES_NAMESPACE = "gmail_rules"
GMAIL_LABEL_OVERRIDES_KEY = "label_overrides"
GMAIL_FULL_HTML_REQUIRED_KEY = "full_html_required"


def normalize_label_override_rules(value: object | None) -> list[GmailLabelOverrideRule]:
    if not isinstance(value, list):
        return []
    rules: list[GmailLabelOverrideRule] = []
    for item in value:
        try:
            rules.append(GmailLabelOverrideRule.model_validate(item))
        except Exception:
            continue
    return rules


def normalize_full_html_rules(value: object | None) -> list[GmailFullHtmlExtractionRule]:
    if not isinstance(value, list):
        return []
    rules: list[GmailFullHtmlExtractionRule] = []
    for item in value:
        try:
            rules.append(GmailFullHtmlExtractionRule.model_validate(item))
        except Exception:
            continue
    return rules


def sender_identity(sender: str | None) -> tuple[str | None, str | None]:
    _, parsed_email = parseaddr(sender or "")
    sender_email = parsed_email.strip().lower() if parsed_email else None
    sender_domain = None
    if sender_email and "@" in sender_email:
        sender_domain = sender_email.rsplit("@", 1)[1].strip().lower() or None
    return sender_email, sender_domain


def sender_rule_matches_message(
    rule: GmailLabelOverrideRule | GmailFullHtmlExtractionRule,
    message: GmailStoredMessage,
) -> bool:
    if not rule.enabled:
        return False
    sender_email, sender_domain = sender_identity(message.sender)
    if rule.match_type == GmailRuleMatchType.SENDER:
        return sender_email == rule.value
    if sender_domain is None:
        return False
    return sender_domain == rule.value or sender_domain.endswith(f".{rule.value}")


def matching_label_override(
    rules: list[GmailLabelOverrideRule],
    message: GmailStoredMessage,
) -> GmailLabelOverrideRule | None:
    for rule in rules:
        if sender_rule_matches_message(rule, message):
            return rule
    return None


def full_html_required(
    rules: list[GmailFullHtmlExtractionRule],
    message: GmailStoredMessage,
) -> bool:
    return any(sender_rule_matches_message(rule, message) for rule in rules)
