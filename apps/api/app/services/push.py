"""Web push for follow-up reminders.

The fallback matters more than the feature. Notifications get denied, revoked
and silently dropped, and on iOS they only work once the site is on the home
screen - so the dashboard's "due today" list is the real mechanism and push is
a convenience on top of it. Nothing here is load-bearing.

A 404 or 410 from a push service means the subscription is dead - the browser
was uninstalled, the user cleared data - and the row should go. Leaving dead
subscriptions in the table means every future send retries them forever.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import delete, select

from ..models import PushSubscription

logger = logging.getLogger(__name__)

GONE_STATUSES = (404, 410)


async def notify(
    session,
    *,
    user_id: uuid.UUID,
    title: str,
    body: str,
    url: str,
    settings,
) -> int:
    """Send to every registered device. Returns how many were delivered."""
    if not settings.vapid_private_key:
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.info("pywebpush is not installed; skipping push")
        return 0

    subscriptions = list(
        await session.scalars(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
    )
    payload = json.dumps({"title": title, "body": body, "url": url})
    delivered = 0
    dead: list[uuid.UUID] = []

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": subscription.keys,
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
            delivered += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in GONE_STATUSES:
                dead.append(subscription.id)
            else:
                logger.info("push failed for %s: %s", subscription.id, status)

    if dead:
        await session.execute(delete(PushSubscription).where(PushSubscription.id.in_(dead)))

    return delivered
