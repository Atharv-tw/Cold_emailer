"""The tick loop: decide who gets mail, from which mailbox, and when.

Rules enforced here, in order:

1. Nothing sends outside the configured window/days.
2. A contact is pinned to the mailbox that sent its first message, so
   follow-ups thread and come from a consistent person.
3. Each mailbox has a daily cap that ramps up over its warmup period.
4. Consecutive sends from one mailbox are separated by a randomised gap.
5. Replies, bounces, unsubscribes and suppression stop the sequence.
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable

from .config import DAY_NAMES, Config, Mailbox
from .sender import Outgoing, PermanentSendError, SendError, send
from .sequences import Sequence
from .store import Store, parse_iso, utcnow
from .templating import lint, render_step

MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(minutes=30)


@dataclass
class TickResult:
    contact_id: int
    email: str
    step: int
    outcome: str  # sent | skipped | failed | stopped | dry-run
    detail: str = ""
    mailbox_id: str = ""


# ------------------------------------------------------------------ scheduling


def _random_time_in_window(cfg: Config, rng: random.Random) -> time:
    start = cfg.sending.window_start
    end = cfg.sending.window_end
    start_s = start.hour * 3600 + start.minute * 60
    end_s = end.hour * 3600 + end.minute * 60
    chosen = rng.randint(start_s, end_s)
    return time(chosen // 3600, (chosen % 3600) // 60, chosen % 60)


def _next_sending_day(day: date, cfg: Config, *, inclusive: bool = True) -> date:
    if not inclusive:
        day += timedelta(days=1)
    for _ in range(21):
        if DAY_NAMES[day.weekday()] in cfg.sending.days:
            return day
        day += timedelta(days=1)
    raise ValueError("no sending days configured in the next three weeks")


def schedule_step(
    now: datetime,
    delay_business_days: int,
    cfg: Config,
    rng: random.Random,
    preferred_hour: int | None = None,
) -> datetime:
    """UTC datetime at which a step becomes due, respecting business days."""
    tz = cfg.sending.tz
    local_now = now.astimezone(tz)

    target = local_now.date()
    if delay_business_days == 0:
        target = _next_sending_day(target, cfg)
    else:
        remaining = delay_business_days
        while remaining > 0:
            target += timedelta(days=1)
            if DAY_NAMES[target.weekday()] in cfg.sending.days:
                remaining -= 1

    if preferred_hour is not None:
        slot = time(preferred_hour, rng.randint(0, 59))
    else:
        slot = _random_time_in_window(cfg, rng)

    candidate = datetime.combine(target, slot, tzinfo=tz)

    if candidate <= local_now:
        if cfg.sending.is_sending_time(local_now) and target == local_now.date():
            candidate = local_now
        else:
            following = _next_sending_day(local_now.date(), cfg, inclusive=False)
            candidate = datetime.combine(following, _random_time_in_window(cfg, rng), tzinfo=tz)

    return candidate.astimezone(timezone.utc)


# --------------------------------------------------------------- mailbox pool


def _local_day_bounds(cfg: Config, now: datetime) -> tuple[datetime, datetime]:
    tz = cfg.sending.tz
    local = now.astimezone(tz)
    start = datetime.combine(local.date(), time(0, 0), tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def remaining_capacity(cfg: Config, store: Store, mailbox: Mailbox, now: datetime) -> int:
    """How many more sends this mailbox may make today."""
    day_start, day_end = _local_day_bounds(cfg, now)
    used = store.sent_between(mailbox.id, day_start, day_end)

    state = store.mailbox_state(mailbox.id)
    first_send = mailbox.first_send_date
    if state["first_send_date"]:
        first_send = date.fromisoformat(state["first_send_date"])

    effective = replace(mailbox, first_send_date=first_send)
    cap = cfg.warmup.cap_for(effective, now.astimezone(cfg.sending.tz).date())
    return max(0, cap - used)


def gap_elapsed(store: Store, mailbox_id: str, now: datetime) -> bool:
    next_allowed = parse_iso(store.mailbox_state(mailbox_id)["next_allowed_at"])
    return next_allowed is None or next_allowed <= now


def available_mailboxes(cfg: Config, store: Store, now: datetime) -> list[Mailbox]:
    """Mailboxes with quota left and their inter-send gap satisfied,
    most spare capacity first so load spreads evenly across the pool."""
    ready = [
        (remaining_capacity(cfg, store, mb, now), mb)
        for mb in cfg.active_mailboxes
        if gap_elapsed(store, mb.id, now)
    ]
    ready = [(capacity, mb) for capacity, mb in ready if capacity > 0]
    ready.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [mb for _, mb in ready]


# -------------------------------------------------------------------- the tick


def tick(
    cfg: Config,
    store: Store,
    sequences: dict[str, Sequence],
    *,
    dry_run: bool = False,
    now: datetime | None = None,
    rng: random.Random | None = None,
    log: Callable[[str], None] = print,
) -> list[TickResult]:
    """Process everything currently due. Safe to call as often as you like."""
    now = now or utcnow()
    rng = rng or random.Random()
    results: list[TickResult] = []

    if not cfg.sending.is_sending_time(now) and not dry_run:
        return results

    budget = cfg.sending.max_per_tick
    for contact in store.due_contacts(now):
        if budget <= 0:
            break

        contact_id = int(contact["id"])
        email = contact["email"]

        if store.is_suppressed(email):
            store.set_contact_status(contact_id, "unsubscribed", "on suppression list")
            results.append(TickResult(contact_id, email, contact["next_step"], "stopped", "suppressed"))
            continue

        sequence = sequences.get(contact["sequence"])
        if sequence is None:
            store.set_contact_status(contact_id, "paused", f"unknown sequence {contact['sequence']!r}")
            results.append(TickResult(contact_id, email, contact["next_step"], "skipped", "unknown sequence"))
            continue

        step_no = int(contact["next_step"])
        step = sequence.step(step_no)
        if step is None:
            store.set_contact_status(contact_id, "completed", f"finished after step {step_no - 1}")
            results.append(TickResult(contact_id, email, step_no, "stopped", "sequence complete"))
            continue

        # Sticky mailbox: follow-ups must come from whoever sent step 1.
        if contact["mailbox_id"]:
            mailbox = cfg.mailbox(contact["mailbox_id"])
            if mailbox is None or not mailbox.enabled:
                store.set_contact_status(contact_id, "paused", f"mailbox {contact['mailbox_id']} unavailable")
                results.append(TickResult(contact_id, email, step_no, "skipped", "mailbox gone"))
                continue
            if not dry_run and (
                not gap_elapsed(store, mailbox.id, now)
                or remaining_capacity(cfg, store, mailbox, now) <= 0
            ):
                continue  # try again on a later tick
        else:
            pool = available_mailboxes(cfg, store, now) if not dry_run else cfg.active_mailboxes
            if not pool:
                continue
            mailbox = pool[0]

        rendered = render_step(
            {"id": step.id, "subject": step.subject, "body": step.body},
            contact,
            cfg.identity,
            thread_subject=contact["thread_subject"],
            rng=rng,
        )
        if not rendered.ok:
            detail = "missing merge fields: " + ", ".join(rendered.missing)
            store.set_contact_status(contact_id, "paused", detail)
            results.append(TickResult(contact_id, email, step_no, "skipped", detail, mailbox.id))
            continue

        for warning in lint(rendered.body):
            log(f"  lint [{email} step {step_no}]: {warning}")

        track_token = secrets.token_urlsafe(16) if cfg.tracking.open_tracking else None
        outgoing = Outgoing(
            to_email=email,
            subject=rendered.subject,
            body=rendered.body,
            in_reply_to=contact["last_msgid"] if step.is_followup else None,
            references=contact["thread_refs"] or "",
            track_token=track_token,
            unsub_token=contact["unsub_token"],
        )

        if dry_run:
            results.append(
                TickResult(contact_id, email, step_no, "dry-run", rendered.subject, mailbox.id)
            )
            budget -= 1
            continue

        try:
            msgid = send(cfg, mailbox, outgoing)
        except PermanentSendError as exc:
            store.record_message(
                contact_id=contact_id, step=step_no, mailbox_id=mailbox.id,
                subject=rendered.subject, body=rendered.body,
                status="failed", error=str(exc), track_token=track_token,
            )
            store.set_contact_status(contact_id, "bounced", str(exc))
            store.suppress(email, reason="hard bounce")
            results.append(TickResult(contact_id, email, step_no, "failed", str(exc), mailbox.id))
            budget -= 1
            continue
        except SendError as exc:
            store.record_message(
                contact_id=contact_id, step=step_no, mailbox_id=mailbox.id,
                subject=rendered.subject, body=rendered.body,
                status="failed", error=str(exc), track_token=track_token,
            )
            if store.attempts_for(contact_id, step_no) >= MAX_ATTEMPTS:
                store.set_contact_status(contact_id, "paused", f"{MAX_ATTEMPTS} failed attempts: {exc}")
                results.append(TickResult(contact_id, email, step_no, "failed", f"gave up: {exc}", mailbox.id))
            else:
                store.set_next_due(contact_id, now + RETRY_DELAY)
                results.append(TickResult(contact_id, email, step_no, "failed", f"will retry: {exc}", mailbox.id))
            budget -= 1
            continue

        store.record_message(
            contact_id=contact_id, step=step_no, mailbox_id=mailbox.id,
            subject=rendered.subject, body=rendered.body,
            status="sent", msgid=msgid, in_reply_to=outgoing.in_reply_to,
            track_token=track_token, at=now,
        )
        store.log_event(contact_id, "sent", f"step {step_no} via {mailbox.id}")

        next_step = sequence.step(step_no + 1)
        if next_step is None:
            store.advance_contact(
                contact_id, next_step=step_no + 1, next_due_at=None, mailbox_id=mailbox.id,
                thread_subject=rendered.subject, msgid=msgid,
                thread_refs=f"{contact['thread_refs'] or ''} {msgid}".strip(),
            )
            store.set_contact_status(contact_id, "completed", "sequence finished")
        else:
            due = schedule_step(now, next_step.delay_business_days, cfg, rng, next_step.send_at_hour)
            store.advance_contact(
                contact_id, next_step=step_no + 1, next_due_at=due, mailbox_id=mailbox.id,
                thread_subject=rendered.subject, msgid=msgid,
                thread_refs=f"{contact['thread_refs'] or ''} {msgid}".strip(),
            )

        gap = rng.randint(cfg.sending.min_gap_seconds, cfg.sending.max_gap_seconds)
        store.mark_mailbox_sent(
            mailbox.id, now + timedelta(seconds=gap),
            now.astimezone(cfg.sending.tz).date(), at=now,
        )

        results.append(TickResult(contact_id, email, step_no, "sent", rendered.subject, mailbox.id))
        budget -= 1

    return results
