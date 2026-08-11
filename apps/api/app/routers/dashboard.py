"""What happened, and what needs doing.

"Due today" is pinned at the top because it is the fallback that works when
web push is denied, revoked, or on a platform that quietly drops it. The
notification is a convenience; this list is the mechanism.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from outreach_core.limits import MAX_TOUCHES

from ..deps import CurrentUser, Db
from ..models import Event, Message, ScheduleRow, Suppression, Target, TargetReply

router = APIRouter(prefix="/v1", tags=["dashboard"])


class DueItem(BaseModel):
    target_id: str
    name: str
    email: str
    company: str
    step: int
    due_at: datetime
    has_draft: bool


class TimelineEntry(BaseModel):
    at: datetime
    type: str
    detail: str


class TargetSummary(BaseModel):
    id: str
    name: str
    email: str
    company: str
    status: str
    status_detail: str
    touches_sent: int
    last_touch_at: datetime | None = None


class SentByDay(BaseModel):
    date: str
    count: int


class ReplyItem(BaseModel):
    target_id: str
    name: str
    company: str
    at: datetime
    # Whether the user has opened it yet. No body here on purpose - the tracker
    # is a list of who answered, and the words live one click away.
    unread: bool = False


class DashboardOut(BaseModel):
    counts: dict[str, int]
    due: list[DueItem]
    recent: list[TimelineEntry]
    targets: list[TargetSummary]
    suppressed: int
    sent_by_day: list[SentByDay]
    replies: list[ReplyItem]


class ScheduledItem(BaseModel):
    target_id: str
    name: str
    email: str
    company: str
    step: int
    due_at: datetime
    # A pending row is a slot, not an email. The worker looks for a draft at
    # that step and skips the row when there is none, so a slot with nothing
    # written sends nothing - and listing it as "queued" promises a send that
    # will not happen. The UI needs to be able to tell the two apart.
    drafted: bool = False
    # Parked by the worker: it was due, nothing was written for long enough
    # that it was clearly not coming, and it is no longer being scanned. Only
    # writing the draft brings it back.
    needs_draft: bool = False
    # Server-side so every surface agrees on what "urgent" means. Lower first:
    # 0 parked, 1 due inside a day and unwritten, 2 everything else.
    urgency: int = 2


class ScheduledOut(BaseModel):
    items: list[ScheduledItem]


class ThreadMessage(BaseModel):
    step: int
    subject: str
    body: str
    status: str
    sent_at: datetime | None = None
    error: str = ""
    # A queued message is still a draft - the state lives on the schedule row,
    # not on the message - so without this the UI cannot tell "written" from
    # "written and going out on Monday".
    queued_for: datetime | None = None


class TargetDetail(BaseModel):
    target: TargetSummary
    messages: list[ThreadMessage]
    timeline: list[TimelineEntry]
    touches_remaining: int
    queued_for: datetime | None = None
    queued_step: int | None = None


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(user: CurrentUser, session: Db) -> DashboardOut:
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=24)

    status_counts = dict(
        (
            await session.execute(
                select(Target.status, func.count(Target.id))
                .where(Target.user_id == user.id)
                .group_by(Target.status)
            )
        ).all()
    )
    sent_total = int(
        await session.scalar(
            select(func.count(Message.id)).where(
                Message.user_id == user.id, Message.status == "sent"
            )
        )
        or 0
    )
    # Targets with at least one follow-up still queued. Counted over distinct
    # targets, not rows, so a sequence with two pending steps is one "scheduled".
    scheduled_total = int(
        await session.scalar(
            select(func.count(func.distinct(ScheduleRow.target_id))).where(
                ScheduleRow.user_id == user.id, ScheduleRow.state == "pending"
            )
        )
        or 0
    )

    due_rows = list(
        await session.scalars(
            select(ScheduleRow)
            .where(
                ScheduleRow.user_id == user.id,
                ScheduleRow.state == "pending",
                ScheduleRow.due_at <= horizon,
            )
            .order_by(ScheduleRow.due_at)
        )
    )

    due: list[DueItem] = []
    for row in due_rows:
        target = await session.get(Target, row.target_id)
        if target is None:
            continue
        draft = await session.scalar(
            select(func.count(Message.id)).where(
                Message.target_id == target.id,
                Message.step == row.step,
                Message.status == "draft",
            )
        )
        due.append(
            DueItem(
                target_id=str(target.id),
                name=target.name,
                email=target.email,
                company=target.company,
                step=row.step,
                due_at=row.due_at,
                has_draft=bool(draft),
            )
        )

    recent = [
        TimelineEntry(at=event.at, type=event.type, detail=event.detail)
        for event in await session.scalars(
            select(Event).where(Event.user_id == user.id).order_by(Event.at.desc()).limit(25)
        )
    ]

    targets = [
        TargetSummary(
            id=str(target.id),
            name=target.name,
            email=target.email,
            company=target.company,
            status=target.status,
            status_detail=target.status_detail,
            touches_sent=target.touches_sent,
            last_touch_at=target.last_touch_at,
        )
        for target in await session.scalars(
            select(Target).where(Target.user_id == user.id).order_by(Target.created_at.desc())
        )
    ]

    suppressed = int(
        await session.scalar(
            select(func.count(Suppression.id)).where(Suppression.user_id == user.id)
        )
        or 0
    )

    # 30-day send trend, zero-filled - the API groups by day but leaves gaps
    # for days nothing sent, and the dashboard tile shouldn't have to guess.
    since = now - timedelta(days=29)
    sent_rows = (
        await session.execute(
            select(func.date(Message.sent_at), func.count(Message.id))
            .where(
                Message.user_id == user.id,
                Message.status == "sent",
                Message.sent_at >= since,
            )
            .group_by(func.date(Message.sent_at))
        )
    ).all()
    sent_by_day_map = {str(day): count for day, count in sent_rows}
    sent_by_day = [
        SentByDay(date=str(day), count=sent_by_day_map.get(str(day), 0))
        for day in (
            (now - timedelta(days=offset)).date() for offset in range(29, -1, -1)
        )
    ]

    # One query, not eleven. This read the ten latest reply events and then
    # issued a `session.get(Target, ...)` per event, which also meant an event
    # whose target had been deleted was silently dropped and the list came back
    # short of the ten it promised. Joining states that intent instead.
    reply_rows = (
        await session.execute(
            select(
                Event.at,
                Target.id,
                Target.name,
                Target.company,
                TargetReply.read_at,
                # Distinguishes "stored and unread" from "no stored reply at
                # all"; both leave `read_at` NULL under the outer join.
                TargetReply.created_at,
            )
            .join(Target, Target.id == Event.target_id)
            .outerjoin(TargetReply, TargetReply.target_id == Target.id)
            .where(Event.user_id == user.id, Event.type == "replied")
            .order_by(Event.at.desc())
            .limit(10)
        )
    ).all()
    replies = [
        ReplyItem(
            target_id=str(target_id),
            name=name,
            company=company,
            at=at,
            # An outer join, because a reply that predates `target_replies`
            # existing has an event and no stored body. Treated as read: there
            # is nothing to open, so marking it unread would be an alert the
            # user can never clear.
            unread=read_at is None and stored_at is not None,
        )
        for at, target_id, name, company, read_at, stored_at in reply_rows
    ]

    # Backed by the partial index on `read_at IS NULL`, so this stays a count
    # of the unread rows rather than a scan of every reply ever received.
    unread_replies = int(
        await session.scalar(
            select(func.count(TargetReply.target_id)).where(
                TargetReply.user_id == user.id, TargetReply.read_at.is_(None)
            )
        )
        or 0
    )

    return DashboardOut(
        counts={
            "sent": sent_total,
            "unread_replies": unread_replies,
            "replied": status_counts.get("replied", 0),
            "bounced": status_counts.get("bounced", 0),
            "opted_out": status_counts.get("opted_out", 0),
            "active": status_counts.get("active", 0),
            "draft": status_counts.get("draft", 0),
            "paused": status_counts.get("paused", 0),
            "completed": status_counts.get("completed", 0),
            "scheduled": scheduled_total,
        },
        due=due,
        recent=recent,
        targets=targets,
        suppressed=suppressed,
        sent_by_day=sent_by_day,
        replies=replies,
    )


@router.get("/dashboard/scheduled", response_model=ScheduledOut)
async def dashboard_scheduled(user: CurrentUser, session: Db) -> ScheduledOut:
    """The full pending follow-up queue, for the dashboard's scheduled-sends
    modal. `/dashboard` itself only carries the next-24h slice of this."""
    now = datetime.now(timezone.utc)
    soon = now + timedelta(hours=24)

    # `needs_draft` too, not only `pending`. A parked row is the one the user
    # most needs to see - it is the follow-up that has already missed its slot -
    # and leaving it out of this list is how it stayed invisible.
    rows = list(
        await session.scalars(
            select(ScheduleRow)
            .where(
                ScheduleRow.user_id == user.id,
                ScheduleRow.state.in_(("pending", "needs_draft")),
            )
            .order_by(ScheduleRow.due_at)
        )
    )

    # One query rather than one per row: this list is unbounded in principle,
    # and the N+1 on targets below is already one too many.
    drafted_steps = {
        (target_id, step)
        for target_id, step in await session.execute(
            select(Message.target_id, Message.step).where(
                Message.user_id == user.id, Message.status == "draft"
            )
        )
    }

    items: list[ScheduledItem] = []
    for row in rows:
        target = await session.get(Target, row.target_id)
        if target is None:
            continue
        drafted = (row.target_id, row.step) in drafted_steps
        needs_draft = row.state == "needs_draft"
        items.append(
            ScheduledItem(
                target_id=str(target.id),
                name=target.name,
                email=target.email,
                company=target.company,
                step=row.step,
                due_at=row.due_at,
                drafted=drafted,
                needs_draft=needs_draft,
                urgency=0 if needs_draft else 1 if (not drafted and row.due_at <= soon) else 2,
            )
        )

    # Urgency first, then the clock inside each band, so "write this one now"
    # sorts above "this goes out on Friday" without losing chronology.
    items.sort(key=lambda item: (item.urgency, item.due_at))
    return ScheduledOut(items=items)


@router.get("/targets/{target_id}/timeline", response_model=TargetDetail)
async def timeline(target_id: uuid.UUID, user: CurrentUser, session: Db) -> TargetDetail:
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user.id)
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such target")

    # step -> when it is due. Only pending rows: a cancelled or sent one is
    # history, and showing it as queued would be a lie.
    pending = {
        row.step: row.due_at
        for row in await session.scalars(
            select(ScheduleRow).where(
                ScheduleRow.target_id == target.id, ScheduleRow.state == "pending"
            )
        )
    }

    # ...and only steps that actually have something written. A pending row on
    # its own sends nothing: the worker looks for a draft for that step and
    # skips the row when there is none. Reporting the row as queued anyway told
    # the user "this is what goes out" above an empty body, and then nothing
    # went out. The schedule row is real, but it is a slot, not a message.
    #
    # This is why the state is not simply "pending or not": a step is queued
    # only where the two agree.
    drafted = set(
        await session.scalars(
            select(Message.step).where(
                Message.target_id == target.id, Message.status == "draft"
            )
        )
    )
    pending = {step: due for step, due in pending.items() if step in drafted}

    messages = [
        ThreadMessage(
            step=message.step,
            subject=message.subject,
            body=message.body,
            status=message.status,
            sent_at=message.sent_at,
            error=message.error,
            queued_for=pending.get(message.step) if message.status == "draft" else None,
        )
        for message in await session.scalars(
            select(Message).where(Message.target_id == target.id).order_by(Message.step)
        )
    ]
    entries = [
        TimelineEntry(at=event.at, type=event.type, detail=event.detail)
        for event in await session.scalars(
            select(Event).where(Event.target_id == target.id).order_by(Event.at)
        )
    ]

    return TargetDetail(
        target=TargetSummary(
            id=str(target.id),
            name=target.name,
            email=target.email,
            company=target.company,
            status=target.status,
            status_detail=target.status_detail,
            touches_sent=target.touches_sent,
            last_touch_at=target.last_touch_at,
        ),
        messages=messages,
        timeline=entries,
        touches_remaining=max(0, MAX_TOUCHES - target.touches_sent),
        # Only ever one, since a step cannot be queued until the one before it
        # has sent - but the earliest is the right answer regardless.
        queued_for=min(pending.values()) if pending else None,
        queued_step=min(pending, key=lambda step: pending[step]) if pending else None,
    )
