"""Keep the calendar in step with the schedule.

Every lifecycle change a follow-up can go through - scheduled, rescheduled,
deferred for an out-of-office, cancelled because they replied or bounced or the
user stopped it - shows up here as a change to a `ScheduleRow`. So mirroring the
rows is enough to mirror all of it, and none of it has to touch the send or
reply paths, where a calendar hiccup could do real harm.

The reconcile is deliberately one-directional. The row is the truth; the
calendar event is a copy. `plan_action` compares the two and says what the
calendar needs, and `sync_user` carries it out best-effort - one failed event
is logged and skipped, never retried in a way that could wedge a user's sync.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import or_, select

from ..models import ScheduleRow, Target, User
from .google_calendar import (
    CalendarAuthRevoked,
    CalendarClient,
    CalendarError,
    build_event_body,
)
from .sending import access_token_for

logger = logging.getLogger(__name__)

# Row states from which a follow-up will never be sent, so any reminder for it
# is stale and should come off the calendar.
_DEAD_STATES = frozenset({"cancelled", "done"})


def plan_action(
    *,
    state: str,
    due_at: datetime,
    google_event_id: str,
    event_synced_due_at: datetime | None,
) -> str:
    """What the calendar needs for one row: create | update | delete | none.

    Pure, so the whole transition table can be checked without a calendar or a
    database behind it.
    """
    if state == "pending":
        if not google_event_id:
            return "create"
        if event_synced_due_at != due_at:
            return "update"
        return "none"
    if google_event_id and state in _DEAD_STATES:
        return "delete"
    return "none"


def _event_for(target: Target, row: ScheduleRow, web_origin: str) -> dict:
    who = target.name or target.email
    lines = [f"Follow up with {who} — touch {row.step}."]
    if target.company:
        lines.append(f"Company: {target.company}")
    if target.email:
        lines.append(f"Email: {target.email}")
    url = f"{web_origin.rstrip('/')}/targets/{target.id}" if web_origin else ""
    if url:
        lines.append(url)
    return build_event_body(
        title=f"Follow up with {who}",
        when=row.due_at,
        description="\n".join(lines),
        url=url,
    )


async def sync_user(
    session,
    *,
    user: User,
    settings,
    calendar: CalendarClient | None = None,
) -> dict:
    """Reconcile one user's calendar with their schedule. Best-effort.

    Returns a small tally for the worker's log. A revoked or absent calendar
    grant stops the pass for this user rather than erroring - the reminder
    layer is optional, and its absence is not a failure of anything else.
    """
    rows = list(
        await session.scalars(
            select(ScheduleRow).where(
                ScheduleRow.user_id == user.id,
                or_(ScheduleRow.state == "pending", ScheduleRow.google_event_id != ""),
            )
        )
    )
    if not rows:
        return {"created": 0, "updated": 0, "deleted": 0}

    client = calendar or CalendarClient(await access_token_for(session, user, settings))
    created = updated = deleted = 0

    for row in rows:
        action = plan_action(
            state=row.state,
            due_at=row.due_at,
            google_event_id=row.google_event_id,
            event_synced_due_at=row.event_synced_due_at,
        )
        if action == "none":
            continue
        try:
            if action == "delete":
                await client.delete_event(row.google_event_id)
                row.google_event_id = ""
                row.event_synced_due_at = None
                deleted += 1
                continue

            target = await session.get(Target, row.target_id)
            if target is None:
                continue
            body = _event_for(target, row, settings.web_origin)
            if action == "create":
                event_id = await client.create_event(body)
                if event_id:
                    row.google_event_id = event_id
                    row.event_synced_due_at = row.due_at
                    created += 1
            else:  # update
                await client.update_event(row.google_event_id, body)
                row.event_synced_due_at = row.due_at
                updated += 1
        except CalendarAuthRevoked:
            # No calendar access. Nothing more can be synced for this user; the
            # event ids we hold are harmless and will be cleaned up if access
            # returns. Not an error worth raising past here.
            logger.info("calendar sync skipped for user %s: no access", user.id)
            break
        except CalendarError as exc:
            # One event failing must not abandon the rest of the pass.
            logger.warning("calendar sync failed for row %s: %s", row.id, exc)
            continue

    return {"created": created, "updated": updated, "deleted": deleted}
