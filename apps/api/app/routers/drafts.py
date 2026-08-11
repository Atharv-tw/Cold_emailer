"""Drafts: generate, edit, and nothing else.

There is no endpoint here that sends. Generating and sending are separate
verbs with separate routes on purpose - the moment "generate" can put mail on
the wire, a retry, a double-click or a bug becomes an email to a stranger.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from outreach_core.limits import MAX_TOUCHES, may_schedule_touch
from outreach_core.templating import lint

from .. import errors
from ..deps import CurrentUser, Db, GeminiKey, SettingsDep
from ..errors import AppError
from ..models import Message, Profile, ProfileExperience, ProfileProject, ScheduleRow, Target
from ..services.gemini import AIError, GeminiClient
from ..services.generation import generate

router = APIRouter(prefix="/v1/targets/{target_id}/draft", tags=["drafts"])


async def _unpark(session, target_id: uuid.UUID, step: int) -> None:
    """Put a `needs_draft` row back in the queue now that there are words for it.

    The worker parks a row that was due with nothing written (worker.py, see
    `NEEDS_DRAFT_AFTER`), which takes it out of the sweep entirely. Writing the
    draft is the thing that was missing, so writing it is what undoes the park -
    otherwise the row is stranded and the send that was scheduled never happens,
    which is the exact failure parking exists to make visible.

    The due time is left alone. It is already in the past, so the next tick
    picks the row up; moving it would silently reschedule a send the user
    thought was overdue.
    """
    row = await session.scalar(
        select(ScheduleRow).where(
            ScheduleRow.target_id == target_id,
            ScheduleRow.step == step,
            ScheduleRow.state == "needs_draft",
        )
    )
    if row is not None:
        row.state = "pending"


class GenerateIn(BaseModel):
    # Free-text steer for a regenerate: "mention the latency work", "warmer".
    instruction: str = Field(default="", max_length=2000)
    template_key: str = Field(default="specific_hook", max_length=80)


class DraftIn(BaseModel):
    subject: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=20000)


class DraftOut(BaseModel):
    target_id: str
    step: int
    subject: str
    body: str
    # lint() output, surfaced inline in the editor rather than blocking a send.
    warnings: list[str]
    is_follow_up: bool
    touches_remaining: int


async def _load(session, user_id, target_id: uuid.UUID):
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user_id)
    )
    if target is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            errors.TARGET_NOT_FOUND,
            "That contact is no longer on your list.",
        )

    decision = may_schedule_touch(
        status=target.status,
        touches_sent=target.touches_sent,
        verification=(target.verification or {}).get("status"),
    )
    if not decision.allowed:
        raise AppError(status.HTTP_409_CONFLICT, errors.SEND_BLOCKED, decision.reason)

    profile = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    projects = list(
        await session.scalars(
            select(ProfileProject).where(ProfileProject.user_id == user_id).order_by(ProfileProject.position)
        )
    )
    experience = list(
        await session.scalars(
            select(ProfileExperience).where(ProfileExperience.user_id == user_id).order_by(ProfileExperience.position)
        )
    )
    return target, profile, projects, experience


async def _sent_thread(session, target_id: uuid.UUID) -> list[tuple[str, str]]:
    rows = await session.scalars(
        select(Message)
        .where(Message.target_id == target_id, Message.status == "sent")
        .order_by(Message.step)
    )
    return [(row.subject, row.body) for row in rows]


def _out(target: Target, message: Message) -> DraftOut:
    return DraftOut(
        target_id=str(target.id),
        step=message.step,
        subject=message.subject,
        body=message.body,
        warnings=lint(message.body),
        is_follow_up=message.step > 1,
        touches_remaining=max(0, MAX_TOUCHES - target.touches_sent),
    )


@router.post("", response_model=DraftOut)
async def generate_draft(
    target_id: uuid.UUID,
    payload: GenerateIn,
    user: CurrentUser,
    session: Db,
    settings: SettingsDep,
    gemini_key: GeminiKey,
) -> DraftOut:
    target, profile, projects, experience = await _load(session, user.id, target_id)
    step = target.touches_sent + 1
    thread = await _sent_thread(session, target.id)

    client = GeminiClient(
        api_key=gemini_key,
        model=settings.gemini_model,
        endpoint=settings.gemini_endpoint,
    )
    try:
        draft = await generate(
            client,
            profile=profile,
            projects=projects,
            experience=experience,
            target=target,
            step=step,
            thread=thread,
            instruction=payload.instruction,
            template_key=payload.template_key,
        )
    except AIError as exc:
        raise AppError(status.HTTP_502_BAD_GATEWAY, errors.AI_FAILED, str(exc)) from exc

    message = await session.scalar(
        select(Message).where(
            Message.target_id == target.id, Message.step == step, Message.status == "draft"
        )
    )
    if message is None:
        message = Message(user_id=user.id, target_id=target.id, step=step, status="draft")
        session.add(message)

    # A follow-up replies in the existing thread, so it keeps that subject.
    message.subject = draft.subject if step == 1 else (target.thread_subject or draft.subject)
    message.body = draft.body
    await _unpark(session, target.id, step)
    await session.commit()
    return _out(target, message)


@router.get("", response_model=DraftOut)
async def read_draft(target_id: uuid.UUID, user: CurrentUser, session: Db) -> DraftOut:
    target, *_ = await _load(session, user.id, target_id)
    step = target.touches_sent + 1
    message = await session.scalar(
        select(Message).where(
            Message.target_id == target.id, Message.step == step, Message.status == "draft"
        )
    )
    if message is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, errors.NO_DRAFT, "Nothing has been drafted yet."
        )
    return _out(target, message)


@router.put("", response_model=DraftOut)
async def save_draft(
    target_id: uuid.UUID, payload: DraftIn, user: CurrentUser, session: Db
) -> DraftOut:
    """Save what the user actually wrote.

    Whatever comes back from here is what gets sent, verbatim. Nothing
    rewrites it, and the lint warnings are advice - a user who wants three
    links in their email is allowed three links in their email.
    """
    target, *_ = await _load(session, user.id, target_id)
    step = target.touches_sent + 1

    message = await session.scalar(
        select(Message).where(
            Message.target_id == target.id, Message.step == step, Message.status == "draft"
        )
    )
    if message is None:
        message = Message(user_id=user.id, target_id=target.id, step=step, status="draft")
        session.add(message)

    if step == 1 and not payload.subject.strip():
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors.MISSING_SUBJECT,
            "A first email needs a subject.",
        )

    message.subject = payload.subject.strip() or target.thread_subject
    message.body = payload.body.rstrip()
    await _unpark(session, target.id, step)
    await session.commit()
    return _out(target, message)
