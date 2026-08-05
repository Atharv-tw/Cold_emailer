"""How the outreach is actually going.

Rates over vanity counts: a reply rate against the people actually contacted
says more than a total of messages sent, and a bounce or opt-out rate is the
number that tells a user their list or their approach needs attention. The
per-facet breakdown answers the one question this product is built around -
which kinds of people are worth writing to - with the user's own results.

Everything here is a read over the caller's own rows under row-level security;
nothing is aggregated across users.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from ..deps import CurrentUser, Db
from ..models import Message, ScheduleRow, Target

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])

# An active sequence whose last touch is older than this has stalled - usually
# a follow-up that came due and was never written.
STALE_AFTER = timedelta(days=7)


class Totals(BaseModel):
    sent: int
    contacted: int
    replied: int
    bounced: int
    opted_out: int
    reply_rate: float
    bounce_rate: float
    opt_out_rate: float


class FacetRow(BaseModel):
    value: str
    contacted: int
    replied: int


class AnalyticsOut(BaseModel):
    totals: Totals
    active_sequences: int
    follow_ups_due: int
    stale: int
    by_target_type: list[FacetRow]
    by_company_type: list[FacetRow]
    by_intent: list[FacetRow]


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


async def _facet(session, user_id, column) -> list[FacetRow]:
    """Contacted vs replied for each distinct value of one facet column."""
    contacted = dict(
        (
            await session.execute(
                select(column, func.count(Target.id))
                .where(Target.user_id == user_id, Target.touches_sent > 0)
                .group_by(column)
            )
        ).all()
    )
    replied = dict(
        (
            await session.execute(
                select(column, func.count(Target.id))
                .where(Target.user_id == user_id, Target.status == "replied")
                .group_by(column)
            )
        ).all()
    )
    values = sorted(set(contacted) | set(replied), key=lambda v: -contacted.get(v, 0))
    return [
        FacetRow(value=value or "unset", contacted=contacted.get(value, 0), replied=replied.get(value, 0))
        for value in values
    ]


@router.get("", response_model=AnalyticsOut)
async def analytics(user: CurrentUser, session: Db) -> AnalyticsOut:
    now = datetime.now(timezone.utc)

    status_counts = dict(
        (
            await session.execute(
                select(Target.status, func.count(Target.id))
                .where(Target.user_id == user.id)
                .group_by(Target.status)
            )
        ).all()
    )
    sent = int(
        await session.scalar(
            select(func.count(Message.id)).where(
                Message.user_id == user.id, Message.status == "sent"
            )
        )
        or 0
    )
    contacted = int(
        await session.scalar(
            select(func.count(Target.id)).where(
                Target.user_id == user.id, Target.touches_sent > 0
            )
        )
        or 0
    )
    replied = status_counts.get("replied", 0)
    bounced = status_counts.get("bounced", 0)
    opted_out = status_counts.get("opted_out", 0)

    follow_ups_due = int(
        await session.scalar(
            select(func.count(ScheduleRow.id)).where(
                ScheduleRow.user_id == user.id,
                ScheduleRow.state == "pending",
                ScheduleRow.due_at <= now,
            )
        )
        or 0
    )
    stale = int(
        await session.scalar(
            select(func.count(Target.id)).where(
                Target.user_id == user.id,
                Target.status == "active",
                Target.last_touch_at.isnot(None),
                Target.last_touch_at < now - STALE_AFTER,
            )
        )
        or 0
    )

    return AnalyticsOut(
        totals=Totals(
            sent=sent,
            contacted=contacted,
            replied=replied,
            bounced=bounced,
            opted_out=opted_out,
            reply_rate=_rate(replied, contacted),
            bounce_rate=_rate(bounced, contacted),
            opt_out_rate=_rate(opted_out, contacted),
        ),
        active_sequences=status_counts.get("active", 0),
        follow_ups_due=follow_ups_due,
        stale=stale,
        by_target_type=await _facet(session, user.id, Target.target_type),
        by_company_type=await _facet(session, user.id, Target.company_type),
        by_intent=await _facet(session, user.id, Target.intent),
    )
