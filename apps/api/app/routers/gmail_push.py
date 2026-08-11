"""The Pub/Sub push endpoint, and push-notification subscriptions.

The Gmail endpoint is unauthenticated in the usual sense - Google posts to it,
not a signed-in user - so it is gated on a shared token in the query string
and on the payload naming an account we actually have. Without that it is an
open POST that anyone could use to make this service hammer Gmail.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import delete, select, text

from ..db import SessionFactory, bind_user
from ..deps import CurrentUser, Db, SettingsDep
from ..models import GmailWatch, PushSubscription, User
from ..services import replies
from ..services.gmail import GmailAuthRevoked, GmailClient, GmailError
from ..services.sending import access_token_for

router = APIRouter(prefix="/v1", tags=["push"])


@router.post("/gmail/push", status_code=status.HTTP_204_NO_CONTENT)
async def gmail_push(
    request: Request, settings: SettingsDep, token: str = Query("")
) -> None:
    """Receive one Gmail change notification.

    Always returns 2xx once the token checks out. Pub/Sub retries anything
    else, and a retry storm caused by our own bug is worse than missing one
    notification - the reconcile sweep exists precisely so that missing one is
    survivable.
    """
    if not settings.pubsub_verification_token or token != settings.pubsub_verification_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bad verification token")

    envelope = await request.json()
    raw = (envelope.get("message") or {}).get("data")
    if not raw:
        return

    try:
        payload = json.loads(base64.b64decode(raw).decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return

    email = str(payload.get("emailAddress", "")).lower()
    history_id = payload.get("historyId")
    if not email or not history_id:
        return

    async with SessionFactory() as session:
        # Pub/Sub is not a signed-in browser request, so there is no user id
        # available to bind before this lookup. An unbound session correctly
        # sees no `users` rows under RLS. This SECURITY DEFINER function answers
        # only the identity question and returns only an id; every read after
        # it is made on the ordinary, user-bound session.
        user_id = await session.scalar(
            text("SELECT find_connected_user_id_by_email(:email)"), {"email": email}
        )
        if user_id is None:
            return
        await bind_user(session, user_id)

        user = await session.get(User, user_id)
        if user is None or user.disconnected_at is not None:
            return

        watch = await session.get(GmailWatch, user.id)
        start = watch.history_id if watch and watch.history_id else None
        if start is None:
            # Nothing to diff against yet; record where we are and wait for
            # the next notification.
            if watch is None:
                watch = GmailWatch(user_id=user.id)
                session.add(watch)
            watch.history_id = int(history_id)
            watch.last_push_at = datetime.now(timezone.utc)
            await session.commit()
            return

        # Stamped before the work below, and kept even when that work fails:
        # the question this answers is whether Pub/Sub can reach us at all,
        # which a Gmail error downstream does not change.
        watch.last_push_at = datetime.now(timezone.utc)

        try:
            gmail = GmailClient(await access_token_for(session, user, settings))
            _, new_history_id = await replies.handle_history(
                session, user=user, gmail=gmail, start_history_id=start
            )
        except GmailAuthRevoked:
            await session.commit()  # keep last_push_at; push itself worked
            return
        except GmailError:
            # Leave the stored history id alone so the next notification -
            # or the reconcile sweep - picks the change up.
            await session.commit()
            return

        if new_history_id is None:
            # The stored id aged out of Gmail's window. Resync directly.
            await replies.reconcile_user(session, user=user, gmail=gmail)
            watch.history_id = int(history_id)
        else:
            watch.history_id = new_history_id
        await session.commit()


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: dict[str, str]


@router.post("/push/subscriptions", status_code=status.HTTP_201_CREATED)
async def subscribe(payload: SubscriptionIn, user: CurrentUser, session: Db) -> dict[str, str]:
    existing = await session.scalar(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == payload.endpoint,
        )
    )
    if existing is None:
        session.add(
            PushSubscription(user_id=user.id, endpoint=payload.endpoint, keys=payload.keys)
        )
    else:
        existing.keys = payload.keys
    await session.commit()
    return {"status": "subscribed"}


@router.delete("/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(payload: SubscriptionIn, user: CurrentUser, session: Db) -> None:
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == payload.endpoint,
        )
    )
    await session.commit()


@router.get("/push/key")
async def public_key(settings: SettingsDep) -> dict[str, str]:
    return {"key": settings.vapid_public_key}
