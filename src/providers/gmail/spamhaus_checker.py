from __future__ import annotations

import asyncio
import socket
from email.utils import parseaddr

from providers.gmail.models import GmailSpamhausCheck


class GmailSpamhausChecker:
    async def check_sender(self, *, account_id: str, message_id: str, sender: str | None) -> GmailSpamhausCheck:
        sender_email = self._extract_sender_email(sender)
        if not sender_email or "@" not in sender_email:
            return GmailSpamhausCheck(
                account_id=account_id,
                message_id=message_id,
                sender_email=sender_email,
                checked=True,
                listed=False,
                status="invalid_sender",
                detail="No valid sender email was available for Spamhaus lookup.",
            )

        sender_domain = sender_email.split("@", 1)[1].lower()
        listed, detail, status = await self._lookup_domain(sender_domain)
        return GmailSpamhausCheck(
            account_id=account_id,
            message_id=message_id,
            sender_email=sender_email,
            sender_domain=sender_domain,
            checked=True,
            listed=listed,
            status=status,
            detail=detail,
        )

    def _extract_sender_email(self, sender: str | None) -> str | None:
        _, address = parseaddr(sender or "")
        return address.lower() or None

    async def _lookup_domain(self, domain: str) -> tuple[bool, str, str]:
        query = f"{domain}.dbl.spamhaus.org"
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, socket.gethostbyname, query)
            return True, "Sender domain is listed in Spamhaus DBL.", "listed"
        except socket.gaierror as exc:
            if exc.errno in {getattr(socket, "EAI_NONAME", -2), getattr(socket, "EAI_NODATA", -5)}:
                return False, "Sender domain is not listed in Spamhaus DBL.", "clean"
            return False, f"Spamhaus lookup failed: {exc}", "error"
