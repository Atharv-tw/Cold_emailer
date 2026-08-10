"""How much mail may go out, to whom, and how often.

Three layers, each with a different failure it prevents:

* **Per target** - a hard ceiling of three touches with a minimum gap, so no
  individual is ever hammered, including by an impatient user.
* **Per user** - a warmup ramp and daily cap, so a new account does not burn
  its sending reputation on day one.
* **Across users** - a keyed guard so one popular recipient cannot receive a
  pile-on from many accounts of this platform at once.

The constants here are the product. They are deliberately not configurable
from the UI: a tool whose limits can be raised by the person who wants to send
more is a tool with no limits.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# A cold sequence is three touches. Not "three by default" - three.
MAX_TOUCHES = 3

# Business days between touches. The scheduler counts these in the user's own
# sending days, so a three-day gap over a weekend is still three working days.
MIN_BUSINESS_DAYS_BETWEEN_TOUCHES = 3

# A finished sequence may start again later, once, after a month. Somebody who
# ignored three emails in April is not necessarily the same prospect in June -
# the student may have shipped something, the company may have started hiring.
#
# The cap is the part that matters, not the interval. At a 30-day cooldown a
# three-week sequence cycles roughly seven times a year, which is over twenty
# emails from one student to one founder; MAX_CYCLES is what turns that into a
# ceiling of six for good, however long the account lives.
#
# The reset works by putting `touches_sent` back to zero and counting the cycle
# separately, which is also what keeps it inside the `touches_sent <=
# MAX_TOUCHES` check constraint in the database. Letting the counter climb to
# six instead would need a migration and would lose that protection.
RESET_AFTER = timedelta(days=30)
MAX_CYCLES = 2

# Statuses from which nothing further may ever be sent. A reply or an opt-out
# is permanent: re-adding the address later must be refused, not merely
# re-scheduled.
TERMINAL_STATUSES = frozenset({"replied", "bounced", "opted_out", "suppressed"})


@dataclass(frozen=True)
class WarmupPolicy:
    """Daily cap that ramps from a new account's first send.

    Ported from the CLI's ``Warmup.cap_for``. The difference is where the
    numbers come from: a per-user database row rather than a YAML file the
    user could edit.
    """

    enabled: bool = True
    start_cap: int = 10
    increment_per_day: int = 3
    max_cap: int = 40

    def cap_for(
        self,
        *,
        daily_cap: int,
        first_send_date: date | None,
        today: date,
    ) -> int:
        """Sends allowed today for an account whose ramp began `first_send_date`."""
        if not self.enabled:
            return daily_cap
        if first_send_date is None:
            # Nothing sent yet: the account is at the bottom of the ramp.
            return min(self.start_cap, daily_cap)
        days_active = (today - first_send_date).days
        ramped = self.start_cap + self.increment_per_day * max(0, days_active)
        return max(1, min(ramped, self.max_cap, daily_cap))


@dataclass(frozen=True)
class TouchDecision:
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


def may_schedule_touch(
    *,
    status: str,
    touches_sent: int,
    verification: str | None = None,
    cycles_used: int = 0,
    last_cycle_ended_at: datetime | None = None,
    now: datetime | None = None,
) -> TouchDecision:
    """Whether another touch may be scheduled for one target.

    Called both when a target is created and again in the worker immediately
    before a send, because state can change between the two - the point of the
    reply-tracking layers is that it often does.

    A completed sequence is not necessarily the end. Once the cooldown has
    passed it may cycle, up to `MAX_CYCLES` - but only from a *silent* target.
    `TERMINAL_STATUSES` is checked first and covers replied, bounced, opted out
    and suppressed, so a cycle can never revive someone who answered or whose
    address failed. That ordering is the safety property; do not reorder it.
    """
    if status in TERMINAL_STATUSES:
        return TouchDecision(False, f"target is {status} - the sequence ended permanently")
    if verification == "undeliverable":
        return TouchDecision(False, "address is undeliverable")
    if touches_sent >= MAX_TOUCHES:
        return _may_start_new_cycle(cycles_used, last_cycle_ended_at, now)
    return TouchDecision(True)


def _may_start_new_cycle(
    cycles_used: int,
    last_cycle_ended_at: datetime | None,
    now: datetime | None,
) -> TouchDecision:
    if cycles_used >= MAX_CYCLES:
        return TouchDecision(
            False,
            f"{cycles_used} of {MAX_CYCLES} sequences already sent - that is the end of it",
        )
    if last_cycle_ended_at is None or now is None:
        # Nothing recorded the end of the last run, so there is no cooldown to
        # measure. Refuse rather than guess: the caller that wants a cycle is
        # the one that has to say when the previous one finished.
        return TouchDecision(False, f"{MAX_TOUCHES} touches already sent")
    waited = now - last_cycle_ended_at
    if waited < RESET_AFTER:
        remaining = (RESET_AFTER - waited).days
        return TouchDecision(False, f"the sequence ended - it may resume in {remaining}d")
    return TouchDecision(True)


def starts_new_cycle(
    *,
    touches_sent: int,
    cycles_used: int,
    last_cycle_ended_at: datetime | None,
    now: datetime,
) -> bool:
    """Whether the next allowed touch begins a fresh sequence.

    Callers need this separately from `may_schedule_touch` because a cycle
    boundary is a write, not just a permission: `touches_sent` goes back to
    zero and `cycles_used` goes up. Asking the same question twice in two
    places is how the two would drift.
    """
    return touches_sent >= MAX_TOUCHES and _may_start_new_cycle(
        cycles_used, last_cycle_ended_at, now
    ).allowed


def remaining_touches(touches_sent: int) -> int:
    return max(0, MAX_TOUCHES - touches_sent)


# ------------------------------------------------------------ cross-user guard


def recipient_key(email: str, secret: bytes) -> str:
    """Stable, unlinkable key for one address.

    A bare hash would not do what the guard needs. The input space of email
    addresses is small and guessable, so anyone holding the table could confirm
    whether a given person is being contacted simply by hashing candidates. A
    keyed HMAC makes the table useless without the secret, which is what lets
    the guard work without the platform accumulating a list of who is being
    emailed.

    The secret must live outside the database holding this table - rotating it
    resets the guard, which is a deliberate trade rather than an accident.
    """
    if not secret:
        raise ValueError("recipient_key needs a non-empty secret")
    normalised = email.strip().lower().encode("utf-8")
    return hmac.new(secret, normalised, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class RecipientGuard:
    """Blocks a pile-on when many accounts contact the same person at once.

    The stored row is a count plus the time of the last contact rather than a
    log of individual sends: keeping the log would rebuild exactly the
    cross-user record of who is being emailed that the hashing is there to
    avoid. The cost is that the window is approximate - a count older than the
    window is treated as stale and starts again, rather than expiring send by
    send. For a guard whose job is to stop obvious pile-ons, that is the right
    side of the trade.
    """

    window: timedelta = timedelta(days=7)
    max_contacts: int = 3

    def is_stale(self, last_contacted_at: datetime | None, now: datetime) -> bool:
        return last_contacted_at is None or (now - last_contacted_at) > self.window

    def blocks(
        self,
        *,
        contact_count: int,
        last_contacted_at: datetime | None,
        now: datetime,
    ) -> bool:
        if self.is_stale(last_contacted_at, now):
            return False
        return contact_count >= self.max_contacts

    def next_count(
        self,
        *,
        contact_count: int,
        last_contacted_at: datetime | None,
        now: datetime,
    ) -> int:
        """Count to store after recording a send at `now`."""
        if self.is_stale(last_contacted_at, now):
            return 1
        return contact_count + 1
