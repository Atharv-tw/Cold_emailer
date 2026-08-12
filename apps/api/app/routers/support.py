"""Reporting a problem, by the same route billing uses to page an operator.

There is no support desk and no platform mailbox - see `routers/billing.py`.
So this sends through the reporting user's own Gmail grant, straight to
`ADMIN_NOTIFY_EMAIL`, and nothing is stored: an issue report isn't a record
this product needs to keep, only a message that needs to arrive.
"""

from __future__ import annotations

from email.message import EmailMessage

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from ..deps import CurrentUser, Db, SettingsDep
from ..errors import AppError
from ..services.gmail import GmailClient, GmailError
from ..services.sending import access_token_for

router = APIRouter(prefix="/v1/support", tags=["support"])

MAX_MESSAGE_CHARS = 4000


class ReportIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ReportOut(BaseModel):
    sent: bool


@router.post("/report", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def report_issue(payload: ReportIn, user: CurrentUser, session: Db, settings: SettingsDep) -> ReportOut:
    text = payload.message.strip()
    if not text:
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "empty_report", "Say a bit about what went wrong.")

    if not settings.admin_notify_email:
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "support_not_configured",
            "Issue reporting isn't set up on this deployment yet.",
        )

    message = EmailMessage()
    message["To"] = settings.admin_notify_email
    message["Subject"] = f"Issue report from {user.email}"
    message.set_content(
        f"Account: {user.name or '(no name)'} <{user.email}>\n\n{text}\n"
    )

    try:
        client = GmailClient(await access_token_for(session, user, settings))
        await client.send(message)
    except GmailError as exc:
        raise AppError(status.HTTP_502_BAD_GATEWAY, "gmail_failed", str(exc)) from exc

    return ReportOut(sent=True)
