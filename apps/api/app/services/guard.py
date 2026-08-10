"""The cross-user pile-on guard, wired to the database.

The failure mode this exists for: one well-known founder gets fifty cold
emails in a week, all from this platform, each from a different user who has
individually stayed inside every limit. Nobody did anything wrong and the
outcome is still indefensible.

The decision logic lives in `outreach_core.limits`; this is the storage side.
The table holds a keyed HMAC of the address and a count - no addresses, and
no per-send log, because keeping one would rebuild exactly the cross-user
record of who is being emailed that the hashing exists to avoid.

**Currently in monitor mode - see `ENFORCE`.** Counts are still recorded, but
nothing is refused on the strength of them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from outreach_core.limits import RecipientGuard, recipient_key

from ..models import RecipientGuardRow

POLICY = RecipientGuard()

# Monitor mode. `record_contact` keeps writing, so the table still accumulates
# a true picture of which addresses many accounts are converging on; the two
# read paths simply decline to act on it. Blocking is off deliberately, not by
# oversight: with a shared contact pool the guard would refuse adds before
# there is enough traffic to know where the real thresholds are, so the counts
# are gathered first and the decision made against data.
#
# Flipping this to True restores enforcement everywhere at once - the call
# sites in `routers/targets.py`, `routers/import_leads.py` and
# `services/sending.py` are left intact for exactly that reason.
ENFORCE = False


async def is_blocked(session: AsyncSession, email: str, secret: bytes, *, now: datetime | None = None) -> bool:
    if not ENFORCE:
        return False
    now = now or datetime.now(timezone.utc)
    key = recipient_key(email, secret)
    row = await session.scalar(
        select(RecipientGuardRow).where(RecipientGuardRow.email_key == key)
    )
    if row is None:
        return False
    return POLICY.blocks(
        contact_count=row.contact_count,
        last_contacted_at=row.last_contacted_at,
        now=now,
    )


async def blocked_emails(
    session: AsyncSession, emails: list[str], secret: bytes, *, now: datetime | None = None
) -> set[str]:
    """Which of these addresses the cross-user guard is currently blocking.

    One query for the whole list rather than one per address: a bulk import
    checks every row it is about to add, and doing that as N round-trips would
    make a large file slow for no reason. Returns the blocked addresses as they
    were passed in, so the caller can match them back to rows.

    Empty while `ENFORCE` is off, which also skips the query entirely.
    """
    if not ENFORCE:
        return set()
    now = now or datetime.now(timezone.utc)
    by_key = {recipient_key(email, secret): email for email in emails if email}
    if not by_key:
        return set()
    rows = await session.scalars(
        select(RecipientGuardRow).where(RecipientGuardRow.email_key.in_(list(by_key)))
    )
    return {
        by_key[row.email_key]
        for row in rows
        if POLICY.blocks(
            contact_count=row.contact_count, last_contacted_at=row.last_contacted_at, now=now
        )
    }


async def record_contact(
    session: AsyncSession, email: str, secret: bytes, *, now: datetime | None = None
) -> int:
    """Note that somebody just contacted this address. Returns the new count.

    Upserted rather than read-then-written: two workers sending to the same
    address at the same moment must not both read a count of two and both
    write three.
    """
    now = now or datetime.now(timezone.utc)
    key = recipient_key(email, secret)

    cutoff = now - POLICY.window

    statement = (
        insert(RecipientGuardRow)
        .values(email_key=key, last_contacted_at=now, contact_count=1)
        .on_conflict_do_update(
            index_elements=[RecipientGuardRow.email_key],
            set_={
                "last_contacted_at": now,
                # Decided inside the statement, against the stored value, so
                # two workers sending to the same address at the same moment
                # cannot both read the same count and both write count + 1.
                # A row older than the window restarts rather than accumulating
                # forever.
                "contact_count": case(
                    (RecipientGuardRow.last_contacted_at > cutoff,
                     RecipientGuardRow.contact_count + 1),
                    else_=1,
                ),
            },
        )
        .returning(RecipientGuardRow.contact_count)
    )
    return int(await session.scalar(statement))
