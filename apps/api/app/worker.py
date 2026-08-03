"""Background jobs.

Four of them, and the reason each exists:

- **tick** - sends what is due. Runs often; does nothing most of the time.
- **renew_watches** - re-arms Gmail push. Google's own guidance is to call
  `watch` once a day, because it expires in about seven days and then stops
  delivering silently. This job existing is the entire reason push can be
  relied on at all.
- **reconcile** - reads threads directly for anything push may have missed.
  Slow, so it runs rarely. It is the reason a broken push pipeline cannot
  cause an email to someone who already replied.
- **notify_due** - web push for follow-ups coming due today.

Not serverless-shaped, which is why the API needs a long-running host.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from .db import SessionFactory, bind_user
from .models import GmailWatch, Message, ScheduleRow, Target, User
from .services import replies
from .services.gmail import GmailAuthRevoked, GmailClient, GmailError
from .services.push import notify
from .services.sending import access_token_for, send_one
from .settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# How many sends one tick will attempt. The per-user gap and daily cap do the
# real limiting; this just stops one pass monopolising the worker.
MAX_SENDS_PER_TICK = 20

# Re-arm a watch well before it lapses rather than on the day.
WATCH_RENEW_BEFORE = timedelta(days=2)


async def _client_for(session, user: User) -> GmailClient:
    return GmailClient(await access_token_for(session, user, settings))


async def _mark_disconnected(session, user: User, reason: str) -> None:
    user.disconnected_at = datetime.now(timezone.utc)
    user.disconnected_reason = reason
    logger.warning("google access lost for user %s: %s", user.id, reason)


async def tick(_ctx: dict) -> dict:
    """Send everything that is due."""
    now = datetime.now(timezone.utc)
    rng = random.Random()
    sent = skipped = 0

    async with SessionFactory() as session:
        due = list(
            await session.scalars(
                select(ScheduleRow)
                .where(ScheduleRow.state == "pending", ScheduleRow.due_at <= now)
                .order_by(ScheduleRow.due_at)
                .limit(MAX_SENDS_PER_TICK * 4)
            )
        )

    for row in due:
        if sent >= MAX_SENDS_PER_TICK:
            break
        async with SessionFactory() as session:
            # Bound per row: the worker acts for one user at a time, so the
            # same row-level security that protects a request protects a job.
            await bind_user(session, row.user_id)
            try:
                schedule = await session.get(ScheduleRow, row.id)
                if schedule is None or schedule.state != "pending":
                    continue

                user = await session.get(User, row.user_id)
                target = await session.get(Target, row.target_id)
                if user is None or target is None:
                    schedule.state = "cancelled"
                    await session.commit()
                    continue

                if user.disconnected_at is not None:
                    skipped += 1
                    continue

                message = await session.scalar(
                    select(Message).where(
                        Message.target_id == target.id,
                        Message.step == schedule.step,
                        Message.status == "draft",
                    )
                )
                if message is None:
                    # Nothing written yet. The dashboard surfaces this as
                    # "due today"; it is not an error.
                    skipped += 1
                    continue

                outcome = await send_one(
                    session,
                    user=user,
                    target=target,
                    message=message,
                    settings=settings,
                    now=datetime.now(timezone.utc),
                    rng=rng,
                )
                if outcome.sent:
                    sent += 1
                elif not outcome.retry:
                    schedule.state = "cancelled"
                    skipped += 1
                else:
                    schedule.attempts += 1
                    skipped += 1
                await session.commit()
            except GmailAuthRevoked as exc:
                user = await session.get(User, row.user_id)
                if user is not None:
                    await _mark_disconnected(session, user, str(exc))
                    await session.commit()
            except Exception:  # noqa: BLE001 - one bad row must not stop the tick
                await session.rollback()
                logger.exception("tick failed for schedule row %s", row.id)

    return {"sent": sent, "skipped": skipped}


async def renew_watches(_ctx: dict) -> dict:
    """Re-arm Gmail push for every connected account.

    Called daily regardless of the stored expiry. `watch` is idempotent, the
    expiry is only approximate, and the failure it guards against is silent -
    so the cheap thing is to call it every day and never wonder.
    """
    if not settings.gmail_pubsub_topic:
        return {"skipped": "no pubsub topic configured"}

    renewed = failed = 0
    async with SessionFactory() as session:
        users = list(await session.scalars(select(User).where(User.disconnected_at.is_(None))))

    for user in users:
        async with SessionFactory() as session:
            await bind_user(session, user.id)
            try:
                current = await session.get(User, user.id)
                if current is None:
                    continue
                gmail = await _client_for(session, current)
                result = await gmail.watch(settings.gmail_pubsub_topic)

                watch = await session.get(GmailWatch, current.id)
                if watch is None:
                    watch = GmailWatch(user_id=current.id)
                    session.add(watch)
                watch.history_id = int(result.get("historyId", 0)) or watch.history_id
                expiration = result.get("expiration")
                if expiration:
                    watch.expires_at = datetime.fromtimestamp(int(expiration) / 1000, tz=timezone.utc)
                watch.last_checked_at = datetime.now(timezone.utc)
                await session.commit()
                renewed += 1
            except GmailAuthRevoked as exc:
                current = await session.get(User, user.id)
                if current is not None:
                    await _mark_disconnected(session, current, str(exc))
                    await session.commit()
                failed += 1
            except GmailError:
                logger.exception("watch renewal failed for user %s", user.id)
                failed += 1

    return {"renewed": renewed, "failed": failed}


async def reconcile(_ctx: dict) -> dict:
    """Safety net: read threads directly for anything push may have missed."""
    checked = stopped = 0
    async with SessionFactory() as session:
        users = list(await session.scalars(select(User).where(User.disconnected_at.is_(None))))

    for user in users:
        async with SessionFactory() as session:
            await bind_user(session, user.id)
            try:
                current = await session.get(User, user.id)
                if current is None:
                    continue
                gmail = await _client_for(session, current)
                outcomes = await replies.reconcile_user(session, user=current, gmail=gmail)
                await session.commit()
                checked += 1
                stopped += sum(1 for outcome in outcomes if outcome.stopped)
            except GmailAuthRevoked as exc:
                current = await session.get(User, user.id)
                if current is not None:
                    await _mark_disconnected(session, current, str(exc))
                    await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()
                logger.exception("reconcile failed for user %s", user.id)

    return {"users_checked": checked, "sequences_stopped": stopped}


async def notify_due(_ctx: dict) -> dict:
    """Tell people what needs writing today.

    Push is the convenience; the dashboard's "due today" list is the thing
    that actually works, including for everyone who denied notifications.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=12)
    notified = 0

    async with SessionFactory() as session:
        rows = list(
            await session.scalars(
                select(ScheduleRow).where(
                    ScheduleRow.state == "pending", ScheduleRow.due_at <= horizon
                )
            )
        )

    by_user: dict = {}
    for row in rows:
        by_user.setdefault(row.user_id, []).append(row)

    for user_id, due in by_user.items():
        async with SessionFactory() as session:
            await bind_user(session, user_id)
            count = len(due)
            await notify(
                session,
                user_id=user_id,
                title="Follow-ups due",
                body=f"{count} follow-up{'s' if count != 1 else ''} to write today.",
                url="/dashboard",
                settings=settings,
            )
            await session.commit()
            notified += 1

    return {"users_notified": notified}


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [tick, renew_watches, reconcile, notify_due]
    cron_jobs = [
        # Often enough that a due send goes out promptly, rarely enough that
        # an idle instance is not spinning.
        cron(tick, minute=set(range(0, 60, 2)), run_at_startup=False),
        # Daily, per Google's guidance for watch.
        cron(renew_watches, hour=3, minute=0),
        # Low frequency by design: it is the backstop, not the mechanism.
        cron(reconcile, hour={1, 7, 13, 19}, minute=30),
        cron(notify_due, hour=8, minute=0),
    ]
    max_jobs = 5
    job_timeout = 300
