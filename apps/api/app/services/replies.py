"""Noticing that someone answered.

Continuing to email a person who already replied is the worst thing this
product can do, so detection has three independent layers and any one of them
is enough:

1. **Push.** `users.watch` on INBOX, delivered through Pub/Sub. Fast, and
   free of polling.
2. **Renewal.** The watch expires in about seven days and then stops
   delivering with no error and no callback. A daily job re-arms every
   connected account, because nothing will tell us when it lapses.
3. **Reconcile.** A slow sweep that reads threads directly for any active
   target not checked recently. It costs more, so it runs rarely - but it
   means total push failure still cannot produce a send to someone who
   replied.

Detection is thread-based: any message in the thread not authored by the user
is inbound. That is more reliable than matching Message-IDs, which clients
drop, rewrite, and mangle.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from outreach_core.classify import Inbound, Verdict, classify

from ..models import DeadAddress, Event, Target, User
from .gmail import GmailClient, GmailError, GmailNotFound
from .sending import stop_sequence, suppress

# How stale an active target's thread may get before the reconcile sweep
# reads it directly.
RECONCILE_AFTER = timedelta(hours=12)


@dataclass(frozen=True)
class ReplyOutcome:
    target_id: str
    verdict: str
    detail: str = ""
    stopped: bool = False
    deferred_until: datetime | None = None


def _decode(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    except (binascii.Error, ValueError):
        return ""


def plain_text(payload: dict) -> str:
    """Pull readable text out of a Gmail message payload.

    Prefers text/plain. Falls back to text/html only because some senders
    write HTML-only replies, and an opt-out inside one still counts.
    """
    parts = [payload]
    plain: list[str] = []
    html: list[str] = []

    while parts:
        part = parts.pop()
        for child in part.get("parts") or []:
            parts.append(child)
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        if mime == "text/plain":
            plain.append(_decode(data))
        elif mime == "text/html":
            html.append(_decode(data))

    if plain:
        return "\n".join(plain)
    import re

    return re.sub(r"<[^>]+>", " ", "\n".join(html))


def delivery_status(payload: dict) -> str:
    """The `message/delivery-status` parts of a bounce, concatenated.

    `plain_text` above deliberately collects only text/plain and text/html, so
    the machine-readable half of a DSN - the part carrying `Status: 5.1.1` -
    never reaches it. Without this, classification has nothing but the subject
    line to go on and cannot tell a dead mailbox from a full one.
    """
    parts = [payload]
    found: list[str] = []

    while parts:
        part = parts.pop()
        for child in part.get("parts") or []:
            parts.append(child)
        if part.get("mimeType") == "message/delivery-status":
            data = (part.get("body") or {}).get("data")
            if data:
                found.append(_decode(data))

    return "\n".join(found)


def headers_of(payload: dict) -> dict[str, str]:
    return {h.get("name", ""): h.get("value", "") for h in (payload.get("headers") or [])}


def _is_from_user(headers: dict[str, str], user_email: str) -> bool:
    sender = headers.get("From", "").lower()
    return user_email.lower() in sender


async def process_thread(
    session, *, user: User, target: Target, gmail: GmailClient, now: datetime | None = None
) -> ReplyOutcome | None:
    """Read one thread and act on anything inbound. Idempotent.

    Returns None when there is nothing new, which is the common case - this
    runs often and most threads are silent.
    """
    now = now or datetime.now(timezone.utc)
    if not target.gmail_thread_id:
        return None

    try:
        thread = await gmail.get_thread(target.gmail_thread_id)
    except GmailNotFound:
        # The user deleted the thread. Nothing to track; stop looking.
        target.thread_checked_at = now
        return None

    target.thread_checked_at = now

    inbound_ids = [
        str(message.get("id"))
        for message in thread.get("messages") or []
        if not _is_from_user(headers_of(message.get("payload") or {}), user.email)
    ]
    if not inbound_ids:
        return None

    # The most recent inbound message is the one that decides the outcome: an
    # out-of-office followed by a real reply must end up as a reply.
    full = await gmail.get_message(inbound_ids[-1])
    payload = full.get("payload") or {}
    inbound = Inbound(
        headers=headers_of(payload),
        body=plain_text(payload),
        delivery_status=delivery_status(payload),
    )
    result = classify(inbound)

    if result.defer is not None:
        # Explicitly not a stop, for either case that lands here. Someone on
        # leave is not someone uninterested, and a full mailbox is not a dead
        # one - treating either as final is the easiest way to lose a lead for
        # no reason.
        deferred = now + result.defer
        await _defer(session, user, target, deferred, result.reason)
        return ReplyOutcome(
            str(target.id), result.verdict.value, result.reason, stopped=False,
            deferred_until=deferred,
        )

    if target.status in ("replied", "bounced", "opted_out"):
        return None  # already handled on an earlier pass

    if result.verdict is Verdict.BOUNCE:
        await stop_sequence(session, user_id=user.id, target=target, status="bounced", detail=result.reason)
        await suppress(session, user_id=user.id, email=target.email, reason="bounced")
        if result.permanent:
            await record_dead_address(session, target.email, result.reason)
    elif result.verdict is Verdict.OPT_OUT:
        await stop_sequence(session, user_id=user.id, target=target, status="opted_out", detail=result.reason)
        await suppress(session, user_id=user.id, email=target.email, reason="asked not to be contacted")
    else:
        await stop_sequence(session, user_id=user.id, target=target, status="replied", detail=result.reason)

    return ReplyOutcome(str(target.id), result.verdict.value, result.reason, stopped=True)


async def record_dead_address(session, email: str, reason: str) -> None:
    """Mark one mailbox dead for every user of this platform, permanently.

    Called only for a parsed 5.x.x delivery status. A bounce recognised by
    subject or sender alone stops the one sequence and goes no further: acting
    on a guess here would burn a good contact for everybody at once.

    Deliberately writes `dead_addresses` and nothing else. Marking the matching
    `contacts` row undeliverable would be a pleasant cache, but the application
    role cannot update a pool row - the UPDATE policy is scoped to rows the
    session owns, so it would match zero rows and succeed, which is the worst
    of both. The pool listing anti-joins this table instead, which needs no
    privilege the request does not have.
    """
    normalised = email.strip().lower()
    await session.execute(
        pg_insert(DeadAddress)
        .values(email=normalised, reason=reason[:500])
        # First bounce wins: the earliest reason is the most useful one, and
        # re-recording would only overwrite it with a later duplicate.
        .on_conflict_do_nothing(index_elements=["email"])
    )


async def is_dead_address(session, email: str) -> bool:
    """Whether this mailbox has already hard-bounced for anyone."""
    return (
        await session.scalar(
            select(DeadAddress.email).where(DeadAddress.email == email.strip().lower())
        )
    ) is not None


async def _defer(session, user: User, target: Target, until: datetime, reason: str) -> None:
    from ..models import ScheduleRow

    rows = await session.scalars(
        select(ScheduleRow).where(
            ScheduleRow.target_id == target.id, ScheduleRow.state == "pending"
        )
    )
    for row in rows:
        if row.due_at < until:
            row.due_at = until
    session.add(
        Event(user_id=user.id, target_id=target.id, type="auto_reply", detail=reason[:500])
    )


async def handle_history(
    session, *, user: User, gmail: GmailClient, start_history_id: int
) -> tuple[list[ReplyOutcome], int | None]:
    """Layer one: process what changed since a history id.

    Returns the outcomes and the new history id. A None history id means the
    stored one was too old and the caller should fall back to reconciling.
    """
    try:
        history = await gmail.history_since(start_history_id)
    except GmailNotFound:
        # Gmail expires history ids. This is expected, not exceptional.
        return [], None

    thread_ids = {
        str(message.get("threadId"))
        for record in history.get("history") or []
        for added in record.get("messagesAdded") or []
        for message in [added.get("message") or {}]
        if message.get("threadId")
    }
    if not thread_ids:
        return [], int(history.get("historyId", start_history_id))

    targets = list(
        await session.scalars(
            select(Target).where(
                Target.user_id == user.id, Target.gmail_thread_id.in_(thread_ids)
            )
        )
    )
    outcomes = []
    for target in targets:
        outcome = await process_thread(session, user=user, target=target, gmail=gmail)
        if outcome is not None:
            outcomes.append(outcome)

    return outcomes, int(history.get("historyId", start_history_id))


async def reconcile_user(
    session, *, user: User, gmail: GmailClient, now: datetime | None = None
) -> list[ReplyOutcome]:
    """Layer three: read threads directly for anything not checked lately.

    Slow and costly, which is why it runs at low frequency. Its job is not to
    be fast; it is to make push failure non-fatal.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - RECONCILE_AFTER

    targets = list(
        await session.scalars(
            select(Target).where(
                Target.user_id == user.id,
                Target.status == "active",
                Target.gmail_thread_id.isnot(None),
                (Target.thread_checked_at.is_(None)) | (Target.thread_checked_at < cutoff),
            )
        )
    )

    outcomes = []
    for target in targets:
        try:
            outcome = await process_thread(session, user=user, target=target, gmail=gmail, now=now)
        except GmailError:
            # One unreadable thread must not abandon the rest of the sweep.
            continue
        if outcome is not None:
            outcomes.append(outcome)
    return outcomes
