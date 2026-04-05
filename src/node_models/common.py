from __future__ import annotations

from typing import Literal


OnboardingStatus = Literal["not_started", "pending", "approved", "rejected", "expired", "consumed", "invalid"]
TrustState = Literal["untrusted", "pending", "trusted", "rejected", "expired", "consumed", "invalid"]
NotificationKind = Literal["popup", "event", "state"]
NotificationSeverity = Literal["info", "success", "warning", "error", "critical"]
NotificationPriority = Literal["low", "normal", "high", "urgent"]
NotificationUrgency = Literal["info", "error", "notification", "urgent", "actions_needed"]
NotificationResultStatus = Literal["accepted", "rejected"]
