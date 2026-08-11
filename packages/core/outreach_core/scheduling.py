"""When a message is allowed to go out.

Ported from the single-user scheduler. The only structural change: every
function takes a :class:`SendingWindow` belonging to one user instead of
reaching into a global config, because there is no global config any more.

Rules enforced here:

1. Nothing is scheduled outside the user's window or on a non-sending day.
2. Business-day delays skip weekends rather than counting calendar days.
3. Times inside the window are randomised, so sends never look like a cron job.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")

# Guard against a window whose days are all non-sending: without a bound the
# search for the next sending day would spin forever.
MAX_LOOKAHEAD_DAYS = 21


class ScheduleError(Exception):
    pass


def resolve_timezone(name: str) -> ZoneInfo:
    """Resolve an IANA name, distinguishing a typo from a missing database.

    Windows ships no IANA timezone database, so without the ``tzdata`` package
    every name looks unknown. That reads as "you typed it wrong" and sends
    people hunting for a typo that isn't there.
    """
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        try:
            import tzdata  # noqa: F401
        except ImportError:
            raise ScheduleError(
                f"Cannot resolve timezone {name!r} - no timezone database is "
                f"installed. Windows does not ship one, so Python needs the "
                f"tzdata package: pip install tzdata"
            ) from exc
        raise ScheduleError(
            f"Unknown timezone {name!r}. Use an IANA name such as "
            f"Asia/Kolkata, Europe/London or America/New_York."
        ) from exc


@dataclass(frozen=True)
class SendingWindow:
    """One user's sending hours. Persisted on the ``profiles`` row."""

    timezone: str = "Asia/Kolkata"
    start: time = time(9, 0)
    end: time = time(17, 0)
    days: tuple[str, ...] = WEEKDAYS
    min_gap_seconds: int = 180
    max_gap_seconds: int = 900

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ScheduleError("window start must be earlier than window end")
        if self.min_gap_seconds > self.max_gap_seconds:
            raise ScheduleError("min_gap_seconds cannot exceed max_gap_seconds")
        unknown = [d for d in self.days if d not in DAY_NAMES]
        if unknown:
            raise ScheduleError(f"unknown sending day(s): {unknown}")
        if not self.days:
            raise ScheduleError("a sending window needs at least one day")

    @property
    def tz(self) -> ZoneInfo:
        return resolve_timezone(self.timezone)

    def is_sending_time(self, moment: datetime) -> bool:
        """True when `moment` (any tz-aware datetime) falls in the window."""
        local = moment.astimezone(self.tz)
        if DAY_NAMES[local.weekday()] not in self.days:
            return False
        return self.start <= local.time() <= self.end

    def gap_seconds(self, rng: random.Random) -> int:
        return rng.randint(self.min_gap_seconds, self.max_gap_seconds)


def random_time_in_window(window: SendingWindow, rng: random.Random) -> time:
    start_s = window.start.hour * 3600 + window.start.minute * 60
    end_s = window.end.hour * 3600 + window.end.minute * 60
    chosen = rng.randint(start_s, end_s)
    return time(chosen // 3600, (chosen % 3600) // 60, chosen % 60)


def next_sending_day(day: date, window: SendingWindow, *, inclusive: bool = True) -> date:
    if not inclusive:
        day += timedelta(days=1)
    for _ in range(MAX_LOOKAHEAD_DAYS):
        if DAY_NAMES[day.weekday()] in window.days:
            return day
        day += timedelta(days=1)
    raise ScheduleError("no sending days configured in the next three weeks")


def add_business_days(start: date, count: int, window: SendingWindow) -> date:
    """Advance `count` sending days from `start`, skipping non-sending days."""
    target = start
    remaining = count
    while remaining > 0:
        target += timedelta(days=1)
        if DAY_NAMES[target.weekday()] in window.days:
            remaining -= 1
    return target


def schedule_step(
    now: datetime,
    delay_business_days: int,
    window: SendingWindow,
    rng: random.Random,
    preferred_hour: int | None = None,
) -> datetime:
    """UTC datetime at which a touch becomes due, respecting business days."""
    tz = window.tz
    local_now = now.astimezone(tz)

    if delay_business_days == 0:
        target = next_sending_day(local_now.date(), window)
    else:
        target = add_business_days(local_now.date(), delay_business_days, window)

    if preferred_hour is not None:
        slot = time(preferred_hour, rng.randint(0, 59))
    else:
        slot = random_time_in_window(window, rng)

    candidate = datetime.combine(target, slot, tzinfo=tz)

    if candidate <= local_now:
        if window.is_sending_time(local_now) and target == local_now.date():
            candidate = local_now
        else:
            following = next_sending_day(local_now.date(), window, inclusive=False)
            candidate = datetime.combine(
                following, random_time_in_window(window, rng), tzinfo=tz
            )

    return candidate.astimezone(timezone.utc)


def local_day_bounds(window: SendingWindow, now: datetime) -> tuple[datetime, datetime]:
    """UTC bounds of the user's local calendar day - the daily cap's unit."""
    tz = window.tz
    local = now.astimezone(tz)
    start = datetime.combine(local.date(), time(0, 0), tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)
