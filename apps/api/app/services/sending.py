"""The send path: every check that stands between a draft and an inbox.

Each check is re-run here, immediately before the send, even when the same
check already passed when the target was created or the draft was written.
That is the point of doing it here. Days pass between those moments, and in
that gap someone can reply, bounce, opt out, or be piled on by other users of
this platform. A limit checked only at creation time is a limit that was true
once.

Order matters: the checks that protect the recipient come before the ones
that protect the sender's reputation, and the cheap ones come before the ones
that cost a network call.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from outreach_core.limits import MAX_TOUCHES, WarmupPolicy, may_schedule_touch
from outreach_core.mime import Outgoing, SenderIdentity, build_message, extend_references
from outreach_core.scheduling import SendingWindow, local_day_bounds, schedule_step
from outreach_core.templating import render_draft

from ..crypto import Secret, decrypt
from ..models import (
    Event, GoogleToken, Message, Profile, ScheduleRow, Suppression, Target, User,
)
from . import guard
from .gmail import (
    GmailAuthRevoked, GmailClient, GmailError, GmailRateLimited,
    exchange_refresh_token,
)

WARMUP = WarmupPolicy()

# Business days between touches, straight from the core constant. Not a
# setting, and not overridable per user.
from outreach_core.limits import MIN_BUSINESS_DAYS_BETWEEN_TOUCHES  # noqa: E402


@dataclass(frozen=True)
class SendOutcome:
    sent: bool
    reason: str = ""
    # True when the caller should try again later rather than give up.
    retry: bool = False
    message_id: str | None = None


def window_for(profile: Profile) -> SendingWindow:
    raw = profile.sending_window or {}
    if not raw:
        return SendingWindow(timezone=profile.timezone or "UTC")
    from datetime import time as _time

    def parse(value: str, fallback: _time) -> _time:
        try:
            hour, minute = (int(part) for part in str(value).split(":")[:2])
            return _time(hour, minute)
        except (TypeError, ValueError):
            return fallback

    return SendingWindow(
        timezone=raw.get("timezone") or profile.timezone or "UTC",
        start=parse(raw.get("start", "09:00"), _time(9, 0)),
        end=parse(raw.get("end", "17:00"), _time(17, 0)),
        days=tuple(raw.get("days") or ("mon", "tue", "wed", "thu", "fri")),
    )


async def access_token_for(session, user: User, settings) -> str:
    """Decrypt the refresh token and trade it for an access token.

    This is the only place a refresh token exists in plaintext, and it does so
    inside a Secret so it cannot land in a log by accident.
    """
    row = await session.scalar(select(GoogleToken).where(GoogleToken.user_id == user.id))
    if row is None:
        raise GmailAuthRevoked("This account is not connected to Google.")

    refresh = Secret(
        decrypt(
            row.refresh_token_enc,
            settings.master_key_bytes,
            aad=str(user.id).encode("ascii"),
        )
    )
    token = await exchange_refresh_token(
        refresh.reveal(), settings.google_client_id, settings.google_client_secret
    )
    return token.token


async def sends_today(session, user_id: uuid.UUID, window: SendingWindow, now: datetime) -> int:
    start, end = local_day_bounds(window, now)
    return int(
        await session.scalar(
            select(func.count(Message.id)).where(
                Message.user_id == user_id,
                Message.status == "sent",
                Message.sent_at >= start,
                Message.sent_at < end,
            )
        )
        or 0
    )


async def last_send_at(session, user_id: uuid.UUID) -> datetime | None:
    return await session.scalar(
        select(func.max(Message.sent_at)).where(
            Message.user_id == user_id, Message.status == "sent"
        )
    )


async def send_one(
    session,
    *,
    user: User,
    target: Target,
    message: Message,
    settings,
    now: datetime | None = None,
    rng: random.Random | None = None,
    force_window: bool = False,
    gmail: GmailClient | None = None,
) -> SendOutcome:
    now = now or datetime.now(timezone.utc)
    rng = rng or random.Random()

    profile = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        return SendOutcome(False, "no profile")
    window = window_for(profile)

    # 1. The recipient's own state. Checked first because it is the only one
    #    where sending anyway is not merely impolite but harmful.
    decision = may_schedule_touch(
        status=target.status,
        touches_sent=target.touches_sent,
        verification=(target.verification or {}).get("status"),
    )
    if not decision.allowed:
        return SendOutcome(False, decision.reason)

    suppressed = await session.scalar(
        select(Suppression).where(
            Suppression.user_id == user.id, Suppression.email == target.email
        )
    )
    if suppressed is not None:
        target.status = "opted_out"
        target.status_detail = suppressed.reason
        return SendOutcome(False, f"suppressed: {suppressed.reason}")

    # 2. Minimum gap between touches for this one person.
    if target.last_touch_at is not None:
        earliest = schedule_step(
            target.last_touch_at, MIN_BUSINESS_DAYS_BETWEEN_TOUCHES, window, rng
        )
        if now < earliest:
            return SendOutcome(False, "too soon since the last touch", retry=True)

    # 3. The cross-user guard.
    if await guard.is_blocked(session, target.email, settings.recipient_guard_secret_bytes, now=now):
        return SendOutcome(
            False,
            "that person is being contacted by too many accounts here at the moment",
        )

    # 4. The sender's own limits: window, daily cap, inter-send gap.
    if not force_window and not window.is_sending_time(now):
        return SendOutcome(False, "outside the sending window", retry=True)

    cap = WARMUP.cap_for(
        daily_cap=profile.daily_cap,
        first_send_date=profile.first_send_date,
        today=now.astimezone(window.tz).date(),
    )
    used = await sends_today(session, user.id, window, now)
    if used >= cap:
        return SendOutcome(False, f"daily cap reached ({used}/{cap})", retry=True)

    previous = await last_send_at(session, user.id)
    if previous is not None:
        gap = timedelta(seconds=window.min_gap_seconds)
        if now - previous < gap:
            return SendOutcome(False, "too soon since the last send", retry=True)

    # 5. Render and send.
    rendered = render_draft(
        message.subject or None,
        message.body,
        {},
        thread_subject=target.thread_subject or None,
    )
    identity = SenderIdentity(email=user.email, from_name=user.name or user.email)
    outgoing = Outgoing(
        to_email=target.email,
        subject=rendered.subject,
        body=rendered.body,
        in_reply_to=target.last_message_id or None,
        references=target.thread_refs or "",
    )

    client = gmail or GmailClient(await access_token_for(session, user, settings))
    try:
        result = await client.send(build_message(identity, outgoing), target.gmail_thread_id)
    except GmailAuthRevoked as exc:
        user.disconnected_at = now
        user.disconnected_reason = str(exc)
        message.status = "failed"
        message.error = str(exc)
        session.add(Event(user_id=user.id, target_id=target.id, type="disconnected", detail=str(exc)))
        return SendOutcome(False, str(exc))
    except GmailRateLimited as exc:
        return SendOutcome(False, f"rate limited: {exc}", retry=True)
    except GmailError as exc:
        message.status = "failed"
        message.error = str(exc)
        return SendOutcome(False, str(exc), retry=True)

    # 6. Record it. Everything below has to happen, or the next touch threads
    #    against nothing and the caps count wrong.
    message.status = "sent"
    message.sent_at = now
    message.gmail_message_id = result.gmail_message_id
    message.rfc822_message_id = result.rfc822_message_id
    message.error = ""

    target.touches_sent += 1
    target.last_touch_at = now
    target.gmail_thread_id = result.thread_id or target.gmail_thread_id
    target.thread_subject = target.thread_subject or rendered.subject
    if result.rfc822_message_id:
        target.last_message_id = result.rfc822_message_id
        target.thread_refs = extend_references(target.thread_refs, result.rfc822_message_id)
    if target.status == "draft":
        target.status = "active"

    if profile.first_send_date is None:
        # The warmup ramp starts from the first send, not from sign-up.
        profile.first_send_date = now.astimezone(window.tz).date()

    await guard.record_contact(session, target.email, settings.recipient_guard_secret_bytes, now=now)
    session.add(
        Event(
            user_id=user.id,
            target_id=target.id,
            type="sent",
            detail=f"touch {target.touches_sent} of {MAX_TOUCHES}",
        )
    )

    await _close_or_advance(session, user, target, window, now, rng)
    return SendOutcome(True, message_id=result.gmail_message_id)


async def _close_or_advance(
    session, user: User, target: Target, window: SendingWindow, now: datetime, rng: random.Random
) -> None:
    """Schedule the next touch, or finish the sequence.

    Nothing is scheduled past the ceiling. The sequence stops itself rather
    than relying on a check at send time to catch it.
    """
    current = await session.scalar(
        select(ScheduleRow).where(
            ScheduleRow.target_id == target.id, ScheduleRow.step == target.touches_sent
        )
    )
    if current is not None:
        current.state = "done"

    if target.touches_sent >= MAX_TOUCHES:
        target.status = "completed"
        target.status_detail = f"all {MAX_TOUCHES} touches sent, no reply"
        return

    next_step = target.touches_sent + 1
    due = schedule_step(now, MIN_BUSINESS_DAYS_BETWEEN_TOUCHES, window, rng)
    existing = await session.scalar(
        select(ScheduleRow).where(
            ScheduleRow.target_id == target.id, ScheduleRow.step == next_step
        )
    )
    if existing is None:
        session.add(
            ScheduleRow(
                user_id=user.id,
                target_id=target.id,
                step=next_step,
                due_at=due,
                state="pending",
            )
        )
    else:
        existing.due_at = due
        existing.state = "pending"


async def stop_sequence(
    session, *, user_id: uuid.UUID, target: Target, status: str, detail: str
) -> None:
    """End a sequence and cancel anything still queued for it."""
    target.status = status
    target.status_detail = detail[:500]
    rows = await session.scalars(
        select(ScheduleRow).where(
            ScheduleRow.target_id == target.id, ScheduleRow.state == "pending"
        )
    )
    for row in rows:
        row.state = "cancelled"
    session.add(Event(user_id=user_id, target_id=target.id, type=status, detail=detail[:500]))


async def suppress(session, *, user_id: uuid.UUID, email: str, reason: str) -> None:
    existing = await session.scalar(
        select(Suppression).where(Suppression.user_id == user_id, Suppression.email == email)
    )
    if existing is None:
        session.add(Suppression(user_id=user_id, email=email, reason=reason[:500]))
