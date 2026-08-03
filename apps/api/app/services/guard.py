"""The cross-user pile-on guard, wired to the database.

The failure mode this exists for: one well-known founder gets fifty cold
emails in a week, all from this platform, each from a different user who has
individually stayed inside every limit. Nobody did anything wrong and the
outcome is still indefensible.

The decision logic lives in `outreach_core.limits`; this is the storage side.
The table holds a keyed HMAC of the address and a count - no addresses, and
no per-send log, because keeping one would rebuild exactly the cross-user
record of who is being emailed that the hashing exists to avoid.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from outreach_core.limits import RecipientGuard, recipient_key

from ..models import RecipientGuardRow

POLICY = RecipientGuard()


async def is_blocked(session: AsyncSession, email: str, secret: bytes, *, now: datetime | None = None) -> bool:
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
