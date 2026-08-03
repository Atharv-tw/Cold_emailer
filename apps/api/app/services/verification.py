"""Is this address real?

Three layers, cheapest first, because the expensive one costs a credit:

1. **Syntax.** A typo like "dana@gmail" never reaches the network.
2. **MX.** A domain with no mail exchanger cannot receive mail from anyone, so
   this is a hard answer rather than a guess, and it is free.
3. **QuickEmailVerification.** Only for addresses that survive the first two.

The four states are ours, not the vendor's. A verifier that says "valid" and a
verifier that says "we could not tell" must not collapse into the same thing:
undeliverable blocks the send, risky warns and lets the user decide, and
unknown gets out of the way. Which brings us to the rule that matters most -
**our own failures map to unknown, never to undeliverable**. If the vendor is
down, out of credits or slow, that is not evidence about somebody's address,
and blocking a send on it would be us inventing a fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

ENDPOINT = "https://api.quickemailverification.com/v1/verify"
SANDBOX_ENDPOINT = "https://api.quickemailverification.com/v1/verify/sandbox"
TIMEOUT_SECONDS = 15

# Deliberately loose. This is here to catch "dana@gmail" and "dana at
# example.com", not to adjudicate RFC 5322 - an over-strict regex rejecting a
# real address is a worse failure than one API call on a typo.
SYNTAX_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

DELIVERABLE = "deliverable"
RISKY = "risky"
UNDELIVERABLE = "undeliverable"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Verification:
    status: str
    reason: str = ""
    # Shown to the user, so it says what to do rather than naming a state.
    detail: str = ""
    did_you_mean: str = ""
    source: str = ""  # syntax | mx | quickemailverification | error
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def blocks_sending(self) -> bool:
        return self.status == UNDELIVERABLE

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
            "did_you_mean": self.did_you_mean,
            "source": self.source,
            "checked_at": self.checked_at.isoformat(),
        }


def normalise(email: str) -> str:
    return email.strip().lower()


def syntax_ok(email: str) -> bool:
    return bool(SYNTAX_RE.match(email)) and len(email) <= 320


def _as_bool(value: Any) -> bool:
    # The API returns booleans as real booleans in some responses and as the
    # strings "true"/"false" in others.
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


async def has_mx(domain: str) -> bool | None:
    """True, False, or None when DNS itself could not answer.

    None matters: a resolver timeout is not the same as a domain with no mail
    exchanger, and treating it as one would block a perfectly good address.
    """
    try:
        import dns.asyncresolver
        import dns.exception
        import dns.resolver
    except ImportError:
        return None

    try:
        answer = await dns.asyncresolver.resolve(domain, "MX", lifetime=5.0)
        return len(answer) > 0
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        # The domain exists but publishes no MX. Some mail still works via an
        # A record fallback, so this is a "probably not" rather than a "no".
        return False
    except dns.exception.DNSException:
        return None


@dataclass(frozen=True)
class EmailVerifier:
    api_key: str = ""
    endpoint: str = ENDPOINT
    # Injectable so the whole decision table can be tested against real
    # response shapes without spending credits.
    transport: httpx.AsyncBaseTransport | None = None
    check_mx: bool = True

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def verify(self, email: str) -> Verification:
        address = normalise(email)

        if not syntax_ok(address):
            return Verification(
                status=UNDELIVERABLE,
                reason="invalid_syntax",
                detail="That is not a valid email address - check for a typo.",
                source="syntax",
            )

        domain = address.rsplit("@", 1)[-1]
        if self.check_mx:
            mx = await has_mx(domain)
            if mx is False:
                return Verification(
                    status=UNDELIVERABLE,
                    reason="no_mx_record",
                    detail=f"{domain} does not accept email - check the spelling of the domain.",
                    source="mx",
                )

        if not self.enabled:
            return Verification(
                status=UNKNOWN,
                reason="verification_not_configured",
                detail="Address verification is not set up, so this has not been checked.",
                source="error",
            )

        return await self._ask_vendor(address)

    async def _ask_vendor(self, address: str) -> Verification:
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS, transport=self.transport
            ) as client:
                # The key goes in the query string because that is the only
                # thing this vendor accepts. It is the one place in this
                # codebase a secret rides in a URL, so nothing here logs the
                # request URL, and errors are built from the status code
                # rather than from the response's echo of the request.
                response = await client.get(
                    self.endpoint,
                    params={"email": address, "apikey": self.api_key},
                )
        except httpx.TimeoutException:
            return _unknown("verifier_timeout", "The address checker timed out, so this has not been verified.")
        except httpx.HTTPError:
            return _unknown("verifier_unreachable", "Could not reach the address checker, so this has not been verified.")

        if response.status_code != 200:
            return _unknown(*_status_reason(response.status_code))

        try:
            payload = response.json()
        except ValueError:
            return _unknown("verifier_malformed", "The address checker returned something unreadable.")

        return _interpret(payload)


def _unknown(reason: str, detail: str) -> Verification:
    return Verification(status=UNKNOWN, reason=reason, detail=detail, source="error")


def _status_reason(code: int) -> tuple[str, str]:
    if code == 401:
        return ("verifier_unauthorised", "The address checker rejected our API key.")
    if code == 402:
        return ("verifier_out_of_credits", "The address checker is out of credits, so this has not been verified.")
    if code == 403:
        return ("verifier_disabled", "The address checker account is disabled.")
    if code == 429:
        return ("verifier_rate_limited", "The address checker is rate limiting us; this has not been verified.")
    return (f"verifier_http_{code}", "The address checker could not answer, so this has not been verified.")


def _interpret(payload: dict[str, Any]) -> Verification:
    """Map one vendor response onto our four states.

    `accept_all` is the interesting case. A catch-all domain accepts anything
    at SMTP time, so "valid" from the vendor means "the server did not say no",
    which is not the same as the mailbox existing. That is risky, not
    deliverable - the user should know they might be writing to nobody.
    """
    if not _as_bool(payload.get("success", True)):
        return _unknown(
            "verifier_reported_failure",
            payload.get("message") or "The address checker could not answer.",
        )

    result = str(payload.get("result", "")).strip().lower()
    reason = str(payload.get("reason", "")).strip().lower()
    did_you_mean = str(payload.get("did_you_mean") or "").strip()

    if result == "invalid":
        detail = "That address does not exist."
        if did_you_mean:
            detail = f"That address does not exist. Did you mean {did_you_mean}?"
        return Verification(
            status=UNDELIVERABLE,
            reason=reason or "invalid",
            detail=detail,
            did_you_mean=did_you_mean,
            source="quickemailverification",
        )

    if result != "valid":
        # "unknown", or anything the vendor adds later. Not evidence either way.
        return Verification(
            status=UNKNOWN,
            reason=reason or result or "unknown",
            detail="The address could not be confirmed either way. You can still send.",
            did_you_mean=did_you_mean,
            source="quickemailverification",
        )

    flags = {
        "disposable": _as_bool(payload.get("disposable")),
        "accept_all": _as_bool(payload.get("accept_all")),
        "role": _as_bool(payload.get("role")),
    }

    if flags["disposable"]:
        return _risky("disposable", "That is a throwaway address - it may not be read.", did_you_mean)
    if flags["accept_all"]:
        return _risky(
            "accept_all",
            "That domain accepts mail to any address, so this one could not be "
            "confirmed to exist. You can still send.",
            did_you_mean,
        )
    if flags["role"]:
        return _risky(
            "role_address",
            "That is a shared address like info@ or support@ rather than a "
            "person. Cold mail to one rarely gets a reply.",
            did_you_mean,
        )

    # safe_to_send is the vendor's own summary judgement. If it disagrees with
    # everything above, take the cautious side.
    if "safe_to_send" in payload and not _as_bool(payload.get("safe_to_send")):
        return _risky(reason or "not_safe_to_send", "The checker flagged this address as risky.", did_you_mean)

    return Verification(
        status=DELIVERABLE,
        reason=reason or "accepted_email",
        detail="Address confirmed.",
        did_you_mean=did_you_mean,
        source="quickemailverification",
    )


def _risky(reason: str, detail: str, did_you_mean: str = "") -> Verification:
    return Verification(
        status=RISKY,
        reason=reason,
        detail=detail,
        did_you_mean=did_you_mean,
        source="quickemailverification",
    )
