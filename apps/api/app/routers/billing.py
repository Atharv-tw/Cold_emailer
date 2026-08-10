"""Buying access to the shared pool, by hand.

There is no payment gateway. The user scans a UPI QR built in their browser,
pays from their own bank app, and uploads a screenshot; an operator looks at it
and decides. So nothing in this file verifies that money moved - it collects a
claim and puts it in a queue, and `routers/admin.py` is where it is believed or
not.

Two orderings here are deliberate and both are about not losing a claim.

**The row is written and committed before the email is attempted.** The
database is the record and the email is a nudge. A user who paid and uploaded
proof must end up in the queue even if their Gmail grant has lapsed, the API
is unreachable, or the operator's address is misconfigured - the failure is
recorded on the row and surfaced in the panel rather than swallowing the claim.

**The upload happens before the row is written.** The row points at an object
key, so writing it first would risk a claim referring to a screenshot that is
not there - which looks, to an operator, exactly like a user who uploaded
nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, Db, SettingsDep
from ..models import PaymentRequest
from ..services import r2
from ..services.gmail import GmailClient, GmailError
from ..services.sending import access_token_for

router = APIRouter(prefix="/v1/billing", tags=["billing"])

# Generous for a phone screenshot, small enough that a mistaken upload of
# something else is refused before it is read into memory in full.
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024


class BillingOut(BaseModel):
    # False when the deployment has no UPI id, no price or no object storage.
    # The purchase page shows "not available yet" rather than a QR that pays
    # nobody, or an upload with nowhere to go.
    available: bool
    price_inr: int
    upi_id: str
    payee_name: str
    # pending | approved | rejected | "" when they have never claimed.
    request_status: str = ""
    requested_at: datetime | None = None
    is_paid: bool = False


class RequestOut(BaseModel):
    id: str
    status: str
    created_at: datetime


@router.get("", response_model=BillingOut)
async def billing_state(user: CurrentUser, session: Db, settings: SettingsDep) -> BillingOut:
    """What the purchase page needs, including this user's open claim."""
    latest = await session.scalar(
        select(PaymentRequest)
        # Filtered by user_id explicitly. `payment_requests` carries no RLS
        # policy - it cannot, because the operator has to read across accounts
        # - so this predicate is the only thing scoping the row, and dropping
        # it would hand one user another user's claim.
        .where(PaymentRequest.user_id == user.id)
        .order_by(PaymentRequest.created_at.desc())
        .limit(1)
    )

    return BillingOut(
        available=settings.billing_configured,
        price_inr=settings.pool_price_inr,
        upi_id=settings.upi_id,
        payee_name=settings.upi_payee_name,
        request_status=latest.status if latest else "",
        requested_at=latest.created_at if latest else None,
        is_paid=user.is_paid,
    )


async def _notify_operator(
    session, settings, user, request: PaymentRequest
) -> str:
    """Tell the operator a claim is waiting. Returns "" or the failure reason.

    Sent through the user's own Gmail grant, because there is no platform
    mailbox - every other email this service sends is a user's. Built here as a
    plain `EmailMessage` rather than through `build_message`, and sent with the
    Gmail client directly rather than through `send_one`: that path applies the
    outreach limiter, records a `RecipientGuard` contact and writes a `Message`
    row, none of which should happen because somebody bought something.

    The body links to the panel rather than carrying the screenshot or a signed
    URL. Signed URLs expire, so one pasted into an inbox is a dead link by the
    time it matters; the panel is durable and already authenticated.
    """
    if not settings.admin_notify_email:
        return "ADMIN_NOTIFY_EMAIL is not set"

    message = EmailMessage()
    message["To"] = settings.admin_notify_email
    message["Subject"] = f"Pool access claim from {user.email}"
    message.set_content(
        "Someone has claimed they paid for the contact pool.\n\n"
        f"Account:   {user.name or '(no name)'} <{user.email}>\n"
        f"Reference: {request.upi_reference or '(none given)'}\n"
        f"Claimed:   {request.created_at:%Y-%m-%d %H:%M %Z}\n\n"
        f"The screenshot and the approve/reject controls are in the admin panel:\n"
        f"{settings.web_origin}/admin\n\n"
        "Nothing has been granted yet.\n"
    )

    try:
        client = GmailClient(await access_token_for(session, user, settings))
        await client.send(message)
    except GmailError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 - the claim matters more than the mail
        return f"{type(exc).__name__}: {exc}"
    return ""


@router.post("/request", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(
    user: CurrentUser,
    session: Db,
    settings: SettingsDep,
    file: UploadFile = File(...),
    upi_reference: str = Form(""),
) -> RequestOut:
    if not settings.billing_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Purchasing is not set up on this deployment."
        )
    if user.is_paid:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have access to the pool.")

    existing = await session.scalar(
        select(PaymentRequest).where(
            PaymentRequest.user_id == user.id, PaymentRequest.status == "pending"
        )
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have a claim waiting to be reviewed."
        )

    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That file is empty.")
    if len(data) > MAX_SCREENSHOT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "That image is larger than 5 MB. A screenshot from your phone will be well under it.",
        )

    # The declared content type is whatever the client chose to send, so the
    # bytes decide. A PDF or an HTML page renamed to .png is refused here
    # rather than stored and later rendered in the operator's browser.
    content_type = r2.sniff_image_type(data)
    if content_type is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "That does not look like a PNG, JPEG or WebP image.",
        )

    key = r2.new_key(content_type)
    try:
        await r2.upload(settings, key=key, data=data, content_type=content_type)
    except r2.R2Error as exc:
        # Nothing written yet, so the user can simply try again.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The screenshot could not be stored. Try again."
        ) from exc

    request = PaymentRequest(
        user_id=user.id,
        screenshot_key=key,
        upi_reference=upi_reference.strip()[:255],
        status="pending",
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)

    # Only now, and never in a way that can fail the request: the claim is
    # already durable, and an operator who is not emailed still sees it.
    error = await _notify_operator(session, settings, user, request)
    if error:
        request.notify_error = error[:2000]
        await session.commit()

    return RequestOut(
        id=str(request.id), status=request.status, created_at=request.created_at
    )
