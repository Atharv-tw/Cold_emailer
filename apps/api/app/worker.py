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
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db import SessionFactory, bind_user
from .models import (
    GmailWatch, GoogleToken, Message, ScheduleRow, Target, User, WorkerHeartbeat,
)
from .services import calendar_sync, replies
from .services.gmail import GmailAuthRevoked, GmailClient, GmailError
from .services.google_oauth import has_calendar_scope
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

# The sweeps. Every job here starts by asking "whose work is waiting?", which
# is a question no bound session can answer and an unbound one answers with
# silence - RLS fails closed, so `select(ScheduleRow)` on an unbound session
# returns zero rows rather than erroring. These are the SECURITY DEFINER
# functions added in 0012; they return ids, and reading anything behind an id
# still means binding to its owner first.
_DUE_ROWS = text("SELECT id, user_id FROM due_schedule_rows(:limit)")
_CONNECTED_USERS = text("SELECT user_id FROM connected_user_ids()")
_PENDING_COUNTS = text("SELECT user_id, pending FROM pending_counts_by_user(:horizon)")


async def _connected_user_ids() -> list:
    """Every account still connected to Google, ids only."""
    async with SessionFactory() as session:
        return list(await session.scalars(_CONNECTED_USERS))


async def _client_for(session, user: User) -> GmailClient:
    return GmailClient(await access_token_for(session, user, settings))


async def _beat(job: str, detail: str = "") -> None:
    """Record that a background job just ran.

    Its own session, unbound: the heartbeat table is outside row-level security
    on purpose, so this does not need - and must not assume - a bound user.
    """
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        await session.execute(
            pg_insert(WorkerHeartbeat)
            .values(job=job, at=now, detail=detail[:500])
            .on_conflict_do_update(
                index_elements=[WorkerHeartbeat.job],
                set_={"at": now, "detail": detail[:500]},
            )
        )
        await session.commit()


async def _mark_disconnected(session, user: User, reason: str) -> None:
    user.disconnected_at = datetime.now(timezone.utc)
    user.disconnected_reason = reason
    logger.warning("google access lost for user %s: %s", user.id, reason)


async def tick(_ctx: dict) -> dict:
    """Send everything that is due."""
    # "Due" is decided by the database's clock inside `due_schedule_rows`, so
    # there is no local `now` here; each send stamps its own.
    rng = random.Random()
    sent = skipped = 0

    async with SessionFactory() as session:
        due = list((await session.execute(_DUE_ROWS, {"limit": MAX_SENDS_PER_TICK * 4})).all())

    for row_id, user_id in due:
        if sent >= MAX_SENDS_PER_TICK:
            break
        async with SessionFactory() as session:
            # Bound per row: the worker acts for one user at a time, so the
            # same row-level security that protects a request protects a job.
            await bind_user(session, user_id)
            try:
                schedule = await session.get(ScheduleRow, row_id)
                if schedule is None or schedule.state != "pending":
                    continue

                user = await session.get(User, user_id)
                target = await session.get(Target, schedule.target_id)
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
                user = await session.get(User, user_id)
                if user is not None:
                    await _mark_disconnected(session, user, str(exc))
                    await session.commit()
            except Exception:  # noqa: BLE001 - one bad row must not stop the tick
                await session.rollback()
                logger.exception("tick failed for schedule row %s", row_id)

    await _beat("tick", f"sent {sent}, skipped {skipped}")
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
    user_ids = await _connected_user_ids()

    for user_id in user_ids:
        async with SessionFactory() as session:
            await bind_user(session, user_id)
            try:
                current = await session.get(User, user_id)
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
                current = await session.get(User, user_id)
                if current is not None:
                    await _mark_disconnected(session, current, str(exc))
                    await session.commit()
                failed += 1
            except GmailError:
                logger.exception("watch renewal failed for user %s", user_id)
                failed += 1

    await _beat("renew_watches", f"renewed {renewed}, failed {failed}")
    return {"renewed": renewed, "failed": failed}


async def reconcile(_ctx: dict) -> dict:
    """Safety net: read threads directly for anything push may have missed."""
    checked = stopped = 0
    user_ids = await _connected_user_ids()

    for user_id in user_ids:
        async with SessionFactory() as session:
            await bind_user(session, user_id)
            try:
                current = await session.get(User, user_id)
                if current is None:
                    continue
                gmail = await _client_for(session, current)
                outcomes = await replies.reconcile_user(session, user=current, gmail=gmail)
                await session.commit()
                checked += 1
                stopped += sum(1 for outcome in outcomes if outcome.stopped)
            except GmailAuthRevoked as exc:
                current = await session.get(User, user_id)
                if current is not None:
                    await _mark_disconnected(session, current, str(exc))
                    await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()
                logger.exception("reconcile failed for user %s", user_id)

    await _beat("reconcile", f"checked {checked}, stopped {stopped}")
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
        by_user = (await session.execute(_PENDING_COUNTS, {"horizon": horizon})).all()

    for user_id, count in by_user:
        async with SessionFactory() as session:
            await bind_user(session, user_id)
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


async def sync_calendars(_ctx: dict) -> dict:
    """Mirror every connected calendar onto the schedule.

    Runs on a short cycle so a newly scheduled, moved, or cancelled follow-up
    shows up as a reminder promptly. Only users who granted the optional
    calendar scope are touched; for everyone else this does nothing. The
    schedule is the source of truth, so a pass that fails for one user changes
    no send and simply retries next time.
    """
    synced = skipped = 0
    user_ids = await _connected_user_ids()

    for user_id in user_ids:
        async with SessionFactory() as session:
            await bind_user(session, user_id)
            try:
                current = await session.get(User, user_id)
                if current is None:
                    continue
                token = await session.get(GoogleToken, current.id)
                if token is None or not has_calendar_scope(token.scopes):
                    skipped += 1
                    continue
                await calendar_sync.sync_user(session, user=current, settings=settings)
                await session.commit()
                synced += 1
            except GmailAuthRevoked as exc:
                current = await session.get(User, user_id)
                if current is not None:
                    await _mark_disconnected(session, current, str(exc))
                    await session.commit()
            except Exception:  # noqa: BLE001 - one user's calendar must not stop the rest
                await session.rollback()
                logger.exception("calendar sync failed for user %s", user_id)

    await _beat("sync_calendars", f"synced {synced}, skipped {skipped}")
    return {"users_synced": synced, "users_skipped": skipped}


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [tick, renew_watches, reconcile, notify_due, sync_calendars]
    cron_jobs = [
        # Often enough that a due send goes out promptly, rarely enough that
        # an idle instance is not spinning.
        cron(tick, minute=set(range(0, 60, 2)), run_at_startup=False),
        # Daily, per Google's guidance for watch.
        cron(renew_watches, hour=3, minute=0),
        # Low frequency by design: it is the backstop, not the mechanism.
        cron(reconcile, hour={1, 7, 13, 19}, minute=30),
        cron(notify_due, hour=8, minute=0),
        # Every five minutes: prompt enough that a reminder tracks a reschedule
        # or a reply without being the source of truth for either.
        cron(sync_calendars, minute=set(range(0, 60, 5))),
    ]
    max_jobs = 5
    job_timeout = 300
