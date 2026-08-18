from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import select, delete

from ..deps import CurrentUser, Db
from ..errors import AppError
from ..models import TrackedThread, TrackedSender

router = APIRouter(prefix="/v1/trackers", tags=["trackers"])


class TrackedThreadIn(BaseModel):
    gmail_thread_id: str
    subject: str = ""


class TrackedThreadOut(BaseModel):
    id: str
    gmail_thread_id: str
    subject: str
    status: str
    notified_at: str | None


class TrackedSenderIn(BaseModel):
    email: str


class TrackedSenderOut(BaseModel):
    id: str
    email: str
    status: str
    last_received_at: str | None


@router.get("/threads", response_model=List[TrackedThreadOut])
async def list_threads(user: CurrentUser, session: Db) -> List[TrackedThreadOut]:
    rows = await session.scalars(select(TrackedThread).where(TrackedThread.user_id == user.id))
    return [
        TrackedThreadOut(
            id=str(r.id),
            gmail_thread_id=r.gmail_thread_id,
            subject=r.subject,
            status=r.status,
            notified_at=r.notified_at.isoformat() if r.notified_at else None
        )
        for r in rows
    ]


@router.post("/threads", response_model=TrackedThreadOut, status_code=status.HTTP_201_CREATED)
async def create_thread(payload: TrackedThreadIn, user: CurrentUser, session: Db) -> TrackedThreadOut:
    existing = await session.scalar(
        select(TrackedThread).where(TrackedThread.user_id == user.id, TrackedThread.gmail_thread_id == payload.gmail_thread_id)
    )
    if existing:
        raise AppError(status.HTTP_409_CONFLICT, "ALREADY_TRACKED", "That thread is already being tracked.")
    
    tt = TrackedThread(
        user_id=user.id,
        gmail_thread_id=payload.gmail_thread_id.strip(),
        subject=payload.subject.strip(),
    )
    session.add(tt)
    await session.commit()
    return TrackedThreadOut(
        id=str(tt.id),
        gmail_thread_id=tt.gmail_thread_id,
        subject=tt.subject,
        status=tt.status,
        notified_at=None
    )


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(thread_id: uuid.UUID, user: CurrentUser, session: Db) -> None:
    await session.execute(delete(TrackedThread).where(TrackedThread.id == thread_id, TrackedThread.user_id == user.id))
    await session.commit()


@router.get("/senders", response_model=List[TrackedSenderOut])
async def list_senders(user: CurrentUser, session: Db) -> List[TrackedSenderOut]:
    rows = await session.scalars(select(TrackedSender).where(TrackedSender.user_id == user.id))
    return [
        TrackedSenderOut(
            id=str(r.id),
            email=r.email,
            status=r.status,
            last_received_at=r.last_received_at.isoformat() if r.last_received_at else None
        )
        for r in rows
    ]


@router.post("/senders", response_model=TrackedSenderOut, status_code=status.HTTP_201_CREATED)
async def create_sender(payload: TrackedSenderIn, user: CurrentUser, session: Db) -> TrackedSenderOut:
    email = payload.email.strip().lower()
    existing = await session.scalar(
        select(TrackedSender).where(TrackedSender.user_id == user.id, TrackedSender.email == email)
    )
    if existing:
        raise AppError(status.HTTP_409_CONFLICT, "ALREADY_TRACKED", "That sender is already being tracked.")
    
    ts = TrackedSender(
        user_id=user.id,
        email=email,
    )
    session.add(ts)
    await session.commit()
    return TrackedSenderOut(
        id=str(ts.id),
        email=ts.email,
        status=ts.status,
        last_received_at=None
    )


@router.delete("/senders/{sender_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sender(sender_id: uuid.UUID, user: CurrentUser, session: Db) -> None:
    await session.execute(delete(TrackedSender).where(TrackedSender.id == sender_id, TrackedSender.user_id == user.id))
    await session.commit()
