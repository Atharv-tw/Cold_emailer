"""The operator's view: who has signed up, and who claims to have paid.

Everything here reads or writes across accounts, which is the one thing the
rest of this service is built to prevent. Two rules keep that honest.

**Nothing here can grant the role it requires.** `is_admin` is set by hand in
SQL and no handler anywhere accepts it - not in a payload, not as a query
parameter. So there is no sequence of requests that turns a signed-in user into
an operator, and a mistake in this file cannot invent one. `POST /users/{id}/plan`
takes `is_paid` and nothing else, deliberately.

**Reading another user's data binds, it does not bypass.** `session_for` is the
same mechanism the worker uses to act for one user at a time: row-level
security stays switched on and the session is bound to the subject instead of
the operator. No connection here has BYPASSRLS. The consequence is that a bug
in this file leaks one account, not all of them.

`users` **is** under RLS, with a self-only policy from 0001 - an earlier version
of this file claimed otherwise and was wrong, which is why the payments list
came back empty while the claim sat in the table: `list_payments` joins to
`users`, and the join dropped every row the operator did not own. 0011 adds
permissive SELECT and UPDATE policies gated on `app.is_admin`, which the
`AdminUser` dependency sets after proving the role. `payment_requests` genuinely
carries no policy - see its docstring for what that costs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from ..db import session_for
from ..deps import AdminUser, Db, SettingsDep
from ..models import Message, PaymentRequest, Target, User
from ..services import r2

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: str
    email: str
    name: str
    joined_at: datetime
    is_paid: bool
    is_admin: bool
    connected: bool


class AdminUserDetailOut(AdminUserOut):
    targets: int
    sent: int
    last_sent_at: datetime | None = None


class PaymentOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_name: str
    upi_reference: str
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None
    note: str
    # Surfaced rather than hidden: a claim whose email never reached the
    # operator is exactly the one at risk of sitting unreviewed.
    notify_error: str


class PlanIn(BaseModel):
    """Deliberately one field.

    A general "patch this user" body is how `is_admin` ends up settable by
    accident. This model cannot carry it, so no amount of extra JSON in the
    request can either - pydantic drops what it does not declare.
    """

    is_paid: bool


class ReviewIn(BaseModel):
    note: str = ""


def _user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        joined_at=user.created_at,
        is_paid=user.is_paid,
        is_admin=user.is_admin,
        connected=user.disconnected_at is None,
    )


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    _: AdminUser,
    session: Db,
    q: str | None = Query(None, description="match on email or name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AdminUserOut]:
    query = select(User).order_by(User.created_at.desc())
    if q and q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{term}%"
        query = query.where(User.email.ilike(like, escape="\\") | User.name.ilike(like, escape="\\"))

    rows = await session.scalars(query.limit(limit).offset(offset))
    return [_user_out(row) for row in rows]


@router.get("/users/{user_id}", response_model=AdminUserDetailOut)
async def get_user(user_id: uuid.UUID, _: AdminUser, session: Db) -> AdminUserDetailOut:
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such user")

    # A second session, bound to the subject rather than the operator. The
    # request's own session is bound to the admin, so counting this user's
    # targets through it would return zero - correctly, and confusingly.
    async with session_for(user.id) as scoped:
        targets = int(
            await scoped.scalar(select(func.count(Target.id)).where(Target.user_id == user.id)) or 0
        )
        sent = int(
            await scoped.scalar(
                select(func.count(Message.id)).where(
                    Message.user_id == user.id, Message.status == "sent"
                )
            )
            or 0
        )
        last_sent_at = await scoped.scalar(
            select(func.max(Message.sent_at)).where(
                Message.user_id == user.id, Message.status == "sent"
            )
        )

    return AdminUserDetailOut(
        **_user_out(user).model_dump(),
        targets=targets,
        sent=sent,
        last_sent_at=last_sent_at,
    )


@router.post("/users/{user_id}/plan", response_model=AdminUserOut)
async def set_plan(
    user_id: uuid.UUID, payload: PlanIn, admin: AdminUser, session: Db
) -> AdminUserOut:
    """Grant or revoke pool access by hand.

    Independent of any payment claim on purpose: comps, refunds, and fixing a
    mistake all need to work without inventing a fake claim to approve.
    """
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such user")

    # An operator removing their own access would still hold the role, so this
    # is recoverable - but it is never what was meant.
    if user.id == admin.id and not payload.is_paid:
        raise HTTPException(status.HTTP_409_CONFLICT, "that would revoke your own access")

    user.is_paid = payload.is_paid
    await session.commit()
    await session.refresh(user)
    return _user_out(user)


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    _: AdminUser,
    session: Db,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
) -> list[PaymentOut]:
    """Claims waiting on a decision, newest first.

    Joined to `users` so the panel can show who is asking without a request per
    row. That join is what made this return nothing before 0011: `users` is
    under RLS, and a session bound to the operator matched only their own
    account, so every claim by anybody else was dropped by the join rather than
    refused. It works now because `AdminUser` elevates the session first.
    """
    query = (
        select(PaymentRequest, User)
        .join(User, User.id == PaymentRequest.user_id)
        .order_by(PaymentRequest.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        query = query.where(PaymentRequest.status == status_filter)

    rows = (await session.execute(query)).all()
    return [
        PaymentOut(
            id=str(request.id),
            user_id=str(request.user_id),
            user_email=user.email,
            user_name=user.name,
            upi_reference=request.upi_reference,
            status=request.status,
            created_at=request.created_at,
            reviewed_at=request.reviewed_at,
            note=request.note,
            notify_error=request.notify_error,
        )
        for request, user in rows
    ]


@router.get("/payments/{payment_id}/screenshot")
async def payment_screenshot(
    payment_id: uuid.UUID, _: AdminUser, session: Db, settings: SettingsDep
) -> RedirectResponse:
    """Redirect to a freshly signed URL for the proof image.

    Minted per request and short-lived, so nothing durable ever points at a
    screenshot showing somebody's UPI handle, phone number and bank. The
    redirect is what lets an `<img src>` in the panel work without the page
    handling credentials.
    """
    request = await session.get(PaymentRequest, payment_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such payment request")
    if not settings.r2_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "object storage is not configured")

    url = r2.presigned_view_url(settings, request.screenshot_key)
    # 302: the signed URL is valid for minutes, so it must never be cached as
    # if it were the permanent location of anything.
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


async def _review(
    session, payment_id: uuid.UUID, admin: User, *, approve: bool, note: str
) -> PaymentOut:
    request = await session.get(PaymentRequest, payment_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such payment request")
    if request.status != "pending":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"that claim was already {request.status}"
        )

    user = await session.scalar(select(User).where(User.id == request.user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "the account that claimed this is gone")

    request.status = "approved" if approve else "rejected"
    request.reviewed_at = datetime.now(timezone.utc)
    request.reviewed_by_user_id = admin.id
    request.note = note
    if approve:
        # Same transaction as the stamp. A commit that granted access without
        # recording why, or recorded it without granting, would both be worse
        # than failing.
        user.is_paid = True

    await session.commit()
    await session.refresh(request)

    return PaymentOut(
        id=str(request.id),
        user_id=str(request.user_id),
        user_email=user.email,
        user_name=user.name,
        upi_reference=request.upi_reference,
        status=request.status,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at,
        note=request.note,
        notify_error=request.notify_error,
    )


@router.post("/payments/{payment_id}/approve", response_model=PaymentOut)
async def approve_payment(
    payment_id: uuid.UUID, admin: AdminUser, session: Db, payload: ReviewIn | None = None
) -> PaymentOut:
    return await _review(
        session, payment_id, admin, approve=True, note=(payload.note if payload else "")
    )


@router.post("/payments/{payment_id}/reject", response_model=PaymentOut)
async def reject_payment(
    payment_id: uuid.UUID, admin: AdminUser, session: Db, payload: ReviewIn | None = None
) -> PaymentOut:
    return await _review(
        session, payment_id, admin, approve=False, note=(payload.note if payload else "")
    )
