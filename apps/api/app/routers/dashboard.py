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
from ..models import Event, Message, ScheduleRow, Suppression, Target

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


class DashboardOut(BaseModel):
    counts: dict[str, int]
    due: list[DueItem]
    recent: list[TimelineEntry]
    targets: list[TargetSummary]
    suppressed: int


class ThreadMessage(BaseModel):
    step: int
    subject: str
    body: str
    status: str
    sent_at: datetime | None = None
    error: str = ""


class TargetDetail(BaseModel):
    target: TargetSummary
    messages: list[ThreadMessage]
    timeline: list[TimelineEntry]
    touches_remaining: int


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

    return DashboardOut(
        counts={
            "sent": sent_total,
            "replied": status_counts.get("replied", 0),
            "bounced": status_counts.get("bounced", 0),
            "opted_out": status_counts.get("opted_out", 0),
            "active": status_counts.get("active", 0),
            "draft": status_counts.get("draft", 0),
            "completed": status_counts.get("completed", 0),
        },
        due=due,
        recent=recent,
        targets=targets,
        suppressed=suppressed,
    )


@router.get("/targets/{target_id}/timeline", response_model=TargetDetail)
async def timeline(target_id: uuid.UUID, user: CurrentUser, session: Db) -> TargetDetail:
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user.id)
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such target")

    messages = [
        ThreadMessage(
            step=message.step,
            subject=message.subject,
            body=message.body,
            status=message.status,
            sent_at=message.sent_at,
            error=message.error,
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
    )
