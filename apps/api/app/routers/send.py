"""Sending, and queueing a send.

Separate from drafts on purpose. Generating text and putting it in front of a
stranger are different acts with different consequences, and they should not
share a route.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import select

from outreach_core.limits import MIN_BUSINESS_DAYS_BETWEEN_TOUCHES
from outreach_core.scheduling import schedule_step

from .. import errors
from ..deps import CurrentUser, Db, SettingsDep
from ..errors import AppError
from ..models import Event, Message, Profile, ScheduleRow, Target
from ..services.gmail import GmailAuthRevoked, GmailError
from ..services.sending import send_one, window_for

router = APIRouter(prefix="/v1/targets/{target_id}", tags=["send"])


class SendResult(BaseModel):
    sent: bool
    reason: str = ""
    scheduled_for: datetime | None = None
    touches_sent: int = 0


async def _target_and_draft(session, user_id, target_id: uuid.UUID):
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user_id)
    )
    if target is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            errors.TARGET_NOT_FOUND,
            "That contact is no longer on your list.",
        )

    step = target.touches_sent + 1
    message = await session.scalar(
        select(Message).where(
            Message.target_id == target.id, Message.step == step, Message.status == "draft"
        )
    )
    if message is None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.NO_DRAFT,
            "There is no draft to send. Write one first, or have it written for you.",
        )
    return target, message, step


@router.post("/send", response_model=SendResult)
async def send_now(
    target_id: uuid.UUID, user: CurrentUser, session: Db, settings: SettingsDep
) -> SendResult:
    """Send the current draft immediately.

    The sending window is bypassed here and only here: the user is sitting in
    front of it, having just read the draft and pressed the button, so
    refusing on the grounds that it is 8pm would be pedantic. Every other
    limit still applies, and the follow-up this schedules lands inside the
    window like anything else.
    """
    target, message, _ = await _target_and_draft(session, user.id, target_id)

    try:
        outcome = await send_one(
            session,
            user=user,
            target=target,
            message=message,
            settings=settings,
            force_window=True,
        )
    except GmailAuthRevoked as exc:
        await session.commit()  # the disconnect is recorded by send_one
        raise AppError(status.HTTP_409_CONFLICT, errors.GMAIL_DISCONNECTED, str(exc)) from exc
    except GmailError as exc:
        raise AppError(status.HTTP_502_BAD_GATEWAY, errors.GMAIL_FAILED, str(exc)) from exc

    await session.commit()
    if not outcome.sent:
        raise AppError(status.HTTP_409_CONFLICT, errors.SEND_BLOCKED, outcome.reason)
    return SendResult(sent=True, touches_sent=target.touches_sent)


@router.post("/schedule", response_model=SendResult)
async def schedule_send(
    target_id: uuid.UUID, user: CurrentUser, session: Db
) -> SendResult:
    """Queue the current draft for the next slot inside the sending window."""
    target, _, step = await _target_and_draft(session, user.id, target_id)

    profile = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.PROFILE_INCOMPLETE,
            "Fill in your profile first - a send needs your sending window from it.",
        )

    window = window_for(profile)
    due = schedule_step(datetime.now(timezone.utc), 0, window, random.Random())

    # Same gap this goes through again at send time (services/sending.py) -
    # checked here too so a reschedule gets a clear refusal instead of
    # silently overwriting a correctly future-dated row with one that will
    # just fail, and keep failing, every time the worker picks it up.
    if target.last_touch_at is not None:
        earliest = schedule_step(
            target.last_touch_at, MIN_BUSINESS_DAYS_BETWEEN_TOUCHES, window, random.Random()
        )
        if due < earliest:
            raise AppError(
                status.HTTP_409_CONFLICT,
                errors.SEND_BLOCKED,
                f"Too soon since the last touch - the earliest this can go out "
                f"is {earliest.isoformat(timespec='minutes')}.",
            )

    existing = await session.scalar(
        select(ScheduleRow).where(ScheduleRow.target_id == target.id, ScheduleRow.step == step)
    )
    if existing is None:
        session.add(
            ScheduleRow(
                user_id=user.id, target_id=target.id, step=step, due_at=due, state="pending"
            )
        )
    else:
        existing.due_at = due
        existing.state = "pending"

    if target.status == "draft":
        target.status = "active"

    # Without this the queue is invisible: the history panel reads events, the
    # message stays a draft until it actually sends, and the due time lives on
    # a row nothing returns - so queueing looked like it had done nothing.
    session.add(
        Event(
            user_id=user.id,
            target_id=target.id,
            type="queued" if existing is None else "requeued",
            detail=f"touch {step} due {due.isoformat(timespec='minutes')}",
        )
    )

    await session.commit()
    return SendResult(sent=False, scheduled_for=due, touches_sent=target.touches_sent)


@router.delete("/schedule", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_schedule(target_id: uuid.UUID, user: CurrentUser, session: Db) -> None:
    rows = list(
        await session.scalars(
            select(ScheduleRow).where(
                ScheduleRow.target_id == target_id,
                ScheduleRow.user_id == user.id,
                # A parked row is cancellable too - "I am not writing this one"
                # is a perfectly good answer to a follow-up nagging in red.
                ScheduleRow.state.in_(("pending", "needs_draft")),
            )
        )
    )
    for row in rows:
        row.state = "cancelled"

    if rows:
        session.add(
            Event(
                user_id=user.id,
                target_id=target_id,
                type="queue_cancelled",
                detail=", ".join(f"touch {row.step}" for row in rows),
            )
        )

    await session.commit()
