"""What an inbound message actually means.

The worst thing this product can do is keep emailing someone who already
replied, so classification has to be right in both directions: a real reply
must stop the sequence, and an out-of-office must *not*, because treating one
as the other silently kills a sequence for someone who is merely on leave.

These are pure functions over headers and body text. Nothing here knows about
IMAP or the Gmail API - the polling loop the CLI used is gone, and callers
hand in whatever their transport gave them. That is what makes the behaviour
testable without a mailbox.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Iterable, Mapping

BOUNCE_SENDERS = ("mailer-daemon", "postmaster", "no-reply", "noreply")
BOUNCE_SUBJECTS = (
    "undeliverable", "delivery status notification", "returned mail",
    "delivery has failed", "mail delivery failed", "address not found",
)
AUTOREPLY_SUBJECTS = (
    "out of office", "automatic reply", "auto-reply", "autoreply",
    "away from my", "on annual leave", "on vacation", "maternity leave",
    "parental leave", "ooo:",
)
UNSUB_PHRASES = (
    "unsubscribe", "remove me", "take me off", "opt out", "opt-out",
    "stop emailing", "do not contact", "don't contact me", "not interested, remove",
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# An auto-responder pauses a sequence rather than ending it. A week is long
# enough to outlast most leave without letting a target go cold.
AUTOREPLY_DEFER = timedelta(days=7)

# Only the top of a long reply is searched for an opt-out phrase, so a quoted
# copy of an older thread cannot trigger a permanent suppression.
OPT_OUT_SCAN_CHARS = 4000


class Verdict(str, Enum):
    REPLY = "reply"
    AUTOREPLY = "autoreply"
    BOUNCE = "bounce"
    OPT_OUT = "opt_out"


@dataclass(frozen=True)
class Inbound:
    """One inbound message, flattened to what classification needs."""

    headers: Mapping[str, str] = field(default_factory=dict)
    body: str = ""

    def header(self, name: str) -> str:
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value or ""
        return ""

    @property
    def subject(self) -> str:
        return self.header("Subject")

    @property
    def from_address(self) -> str:
        raw = self.header("From")
        match = EMAIL_RE.search(raw)
        return match.group(0).lower() if match else raw.strip().lower()

    @classmethod
    def from_gmail(cls, headers: Iterable[Mapping[str, str]], body: str = "") -> "Inbound":
        """Build from a Gmail API ``payload.headers`` list."""
        return cls(
            headers={h.get("name", ""): h.get("value", "") for h in headers},
            body=body,
        )


@dataclass(frozen=True)
class Classification:
    verdict: Verdict
    reason: str = ""
    # Set only for auto-responders: how long to pause before resuming.
    defer: timedelta | None = None

    @property
    def stops_sequence(self) -> bool:
        return self.verdict is not Verdict.AUTOREPLY

    @property
    def suppresses(self) -> bool:
        """Whether the address goes on the user's suppression list."""
        return self.verdict in (Verdict.BOUNCE, Verdict.OPT_OUT)


def is_autoreply(inbound: Inbound) -> bool:
    if (
        inbound.header("Auto-Submitted").lower().startswith("auto")
        or inbound.header("X-Autoreply")
        or inbound.header("X-Autorespond")
        or inbound.header("Precedence").lower() in ("auto_reply", "bulk")
    ):
        return True
    lowered = inbound.subject.lower()
    return any(marker in lowered for marker in AUTOREPLY_SUBJECTS)


def is_bounce(inbound: Inbound) -> bool:
    local = inbound.from_address.split("@", 1)[0]
    if any(marker in local for marker in BOUNCE_SENDERS):
        return True
    lowered = inbound.subject.lower()
    return any(marker in lowered for marker in BOUNCE_SUBJECTS)


def opt_out_phrase(inbound: Inbound) -> str | None:
    haystack = f"{inbound.subject}\n{inbound.body[:OPT_OUT_SCAN_CHARS]}".lower()
    return next((phrase for phrase in UNSUB_PHRASES if phrase in haystack), None)


def bounced_addresses(inbound: Inbound) -> set[str]:
    """Addresses named in a bounce body - the one that actually failed."""
    return {match.lower() for match in EMAIL_RE.findall(inbound.body)}


def classify(inbound: Inbound) -> Classification:
    """Decide what one inbound message means for the sequence.

    Order matters. An auto-responder is checked before the opt-out phrases
    because vacation replies routinely carry a corporate footer containing the
    word "unsubscribe", and reading that as a request to be left alone would
    permanently suppress someone who never asked for anything. A human who
    genuinely wants out will not have ``Auto-Submitted: auto-replied`` on their
    message.
    """
    if is_bounce(inbound):
        return Classification(Verdict.BOUNCE, inbound.subject[:200])

    if is_autoreply(inbound):
        return Classification(
            Verdict.AUTOREPLY, inbound.subject[:200], defer=AUTOREPLY_DEFER
        )

    phrase = opt_out_phrase(inbound)
    if phrase:
        return Classification(Verdict.OPT_OUT, f"reply contained {phrase!r}")

    return Classification(Verdict.REPLY, inbound.subject[:200])
