"""Every email ever sent, across all targets - the Sent Emails page.

`is_reply` and `is_undeliverable` are read off the parent target, not the
individual message: the data model tracks a reply/bounce at the thread level
(`Target.status`), not against one specific step, so this reports "the target
this thread belongs to has replied" rather than false per-message precision.
`is_undeliverable` is only ever true when a `Suppression` row exists - never
inferred from `Message.status == "failed"`, since a failed send can be
transient (rate limit, network blip) and doesn't mean the address is bad.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, Db
from ..models import Message, Suppression, Target

router = APIRouter(prefix="/v1/messages", tags=["messages"])


class MessageOut(BaseModel):
    id: str
    target_id: str
    target_name: str
    target_company: str
    target_email: str
    step: int
    subject: str
    body: str
    status: str
    sent_at: datetime | None = None
    error: str = ""
    is_reply: bool
    is_undeliverable: bool


@router.get("", response_model=list[MessageOut])
async def list_messages(
    user: CurrentUser,
    session: Db,
    status: str | None = Query(None),
    target_id: str | None = Query(None),
    q: str | None = Query(None),
) -> list[MessageOut]:
    query = (
        select(Message, Target)
        .join(Target, Message.target_id == Target.id)
        .where(Message.user_id == user.id)
    )
    if status:
        query = query.where(Message.status == status)
    if target_id:
        query = query.where(Message.target_id == target_id)
    if q:
        like = f"%{q}%"
        query = query.where(
            Target.name.ilike(like) | Target.company.ilike(like) | Message.subject.ilike(like)
        )
    query = query.order_by(Message.sent_at.desc().nulls_last(), Message.created_at.desc())

    rows = (await session.execute(query)).all()

    suppressed = set(
        await session.scalars(select(Suppression.email).where(Suppression.user_id == user.id))
    )

    return [
        MessageOut(
            id=str(message.id),
            target_id=str(target.id),
            target_name=target.name,
            target_company=target.company,
            target_email=target.email,
            step=message.step,
            subject=message.subject,
            body=message.body,
            status=message.status,
            sent_at=message.sent_at,
            error=message.error,
            is_reply=target.status == "replied",
            is_undeliverable=target.email in suppressed,
        )
        for message, target in rows
    ]
