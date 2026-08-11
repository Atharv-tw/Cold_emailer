"""Operational health, for the person running their own outreach.

The failures this surfaces are the quiet ones - a background worker that
stopped, a Gmail watch that lapsed, a Google grant that was revoked, a send
that failed days ago. None of them raise an error at the time; each just makes
the product slowly stop working. This endpoint is where they become visible.

Everything is scoped to the caller except the worker heartbeat, which is a
single non-private timestamp shared by the whole deployment: whether the
background process ran recently is not one user's secret.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from ..deps import CurrentUser, Db
from ..models import GmailWatch, Message, ScheduleRow, Target, User, WorkerHeartbeat

router = APIRouter(prefix="/v1/ops", tags=["ops"])

# Tick runs every two minutes; no heartbeat in ten means the worker is down.
WORKER_STALE_AFTER = timedelta(minutes=10)

# How long an armed watch may deliver nothing before that is worth reporting.
# Generous, because silence is only evidence when mail was expected: a quiet
# mailbox produces no notifications and is not broken. Two days is long enough
# that ordinary quiet does not trip it and short enough to catch a subscription
# pointed at the wrong host before a whole sequence runs its course.
PUSH_SILENT_AFTER = timedelta(days=2)


class JobBeat(BaseModel):
    job: str
    at: datetime
    detail: str


class FailedSend(BaseModel):
    target_id: str
    email: str
    error: str
    at: datetime | None = None


class OpsOut(BaseModel):
    worker_running: bool
    jobs: list[JobBeat]
    connected: bool
    disconnected_reason: str
    watch_last_renewed: datetime | None = None
    watch_expires_at: datetime | None = None
    watch_healthy: bool
    last_push_at: datetime | None = None
    # A watch Gmail accepted, delivering nothing. `watch_healthy` cannot see
    # this: it goes green the moment `watch` returns and stays green for a week
    # whether or not one notification ever arrives.
    push_silent: bool = False
    reconcile_last_read: datetime | None = None
    follow_ups_due: int
    failed_sends: list[FailedSend]


@router.get("", response_model=OpsOut)
async def ops(user: CurrentUser, session: Db) -> OpsOut:
    now = datetime.now(timezone.utc)

    beats = list(await session.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.job)))
    tick_at = next((b.at for b in beats if b.job == "tick"), None)
    worker_running = tick_at is not None and (now - tick_at) < WORKER_STALE_AFTER

    watch = await session.scalar(select(GmailWatch).where(GmailWatch.user_id == user.id))
    watch_expires = watch.expires_at if watch else None
    last_push = watch.last_push_at if watch else None

    reconcile_last = await session.scalar(
        select(func.max(Target.thread_checked_at)).where(Target.user_id == user.id)
    )

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

    failed_rows = list(
        await session.scalars(
            select(Message)
            .where(Message.user_id == user.id, Message.status == "failed")
            .order_by(Message.updated_at.desc())
            .limit(10)
        )
    )
    failed_sends: list[FailedSend] = []
    for message in failed_rows:
        target = await session.get(Target, message.target_id)
        failed_sends.append(
            FailedSend(
                target_id=str(message.target_id),
                email=target.email if target else "",
                error=message.error,
                at=message.updated_at,
            )
        )

    return OpsOut(
        worker_running=worker_running,
        jobs=[JobBeat(job=b.job, at=b.at, detail=b.detail) for b in beats],
        connected=user.disconnected_at is None,
        disconnected_reason=user.disconnected_reason,
        watch_last_renewed=watch.last_checked_at if watch else None,
        watch_expires_at=watch_expires,
        watch_healthy=watch_expires is not None and watch_expires > now,
        last_push_at=last_push,
        push_silent=(
            watch_expires is not None
            and watch_expires > now
            and (last_push is None or (now - last_push) > PUSH_SILENT_AFTER)
        ),
        reconcile_last_read=reconcile_last,
        follow_ups_due=follow_ups_due,
        failed_sends=failed_sends,
    )
