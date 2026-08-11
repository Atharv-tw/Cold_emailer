"""Sign-in, session, and the connected Google account.

The refresh token arrives here once and is encrypted before it touches the
database. No endpoint in this file - or any other - returns it, and no log line
prints it. It is decrypted in memory at send time and nowhere else.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text

from ..crypto import encrypt
from ..db import SessionFactory, bind_user
from ..deps import CurrentUser, Db, SettingsDep
from ..models import GmailWatch, GoogleToken, Profile, User
from ..security import COOKIE_NAME, issue_session
from ..settings import Settings
from ..services.google_oauth import (
    GoogleAuthError,
    has_calendar_scope,
    missing_scopes,
    verify_id_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


async def _arm_watch(session, user: User, settings: Settings) -> None:
    """Register Gmail push for a freshly connected account.

    `renew_watches` in the worker runs at 03:00, and it was the only caller of
    `watch` anywhere - so an account that connected at any other hour had no
    push subscription at all until the next morning. Reply detection fell back
    to the reconcile sweep for up to seventeen hours, on the exact day a new
    user is most likely to be watching for it to work.

    Skipped when a live watch already exists, so the ordinary case - signing in
    again on a connected account - costs nothing. Errors are logged and
    swallowed: sign-in must not fail because Pub/Sub is misconfigured, and the
    daily job is still there to catch up.
    """
    if not settings.gmail_pubsub_topic:
        return

    now = datetime.now(timezone.utc)
    watch = await session.get(GmailWatch, user.id)
    if watch is not None and watch.expires_at is not None and watch.expires_at > now:
        return

    from ..services.gmail import GmailClient, GmailError
    from ..services.sending import access_token_for

    try:
        gmail = GmailClient(await access_token_for(session, user, settings))
        result = await gmail.watch(settings.gmail_pubsub_topic)
    except GmailError:
        logger.exception("could not arm gmail watch for user %s", user.id)
        return

    if watch is None:
        watch = GmailWatch(user_id=user.id)
        session.add(watch)
    watch.history_id = int(result.get("historyId", 0)) or watch.history_id
    expiration = result.get("expiration")
    if expiration:
        watch.expires_at = datetime.fromtimestamp(int(expiration) / 1000, tz=timezone.utc)
    watch.last_checked_at = now
    await session.commit()


class GoogleSignIn(BaseModel):
    id_token: str = Field(min_length=1)
    # Google issues a refresh token only on the first consent, so a returning
    # user signing in again legitimately has none to send.
    refresh_token: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class SessionOut(BaseModel):
    id: str
    email: str
    name: str
    avatar: str
    connected: bool
    missing_scopes: list[str]
    profile_complete: bool
    # Whether the optional calendar-reminder scope was granted.
    calendar_connected: bool = False
    # Entitlement and role. The web app fetches this endpoint on every page
    # load rather than trusting the sign-in JWT, so these are the freshest
    # answer available - a grant made in the admin panel takes effect on the
    # user's next navigation rather than their next sign-in.
    is_paid: bool = False
    is_admin: bool = False


def _session_out(
    user: User,
    settings: Settings,
    *,
    connected: bool,
    missing: list[str],
    profile: Profile | None,
    scopes: list[str] | None = None,
) -> SessionOut:
    avatar = (
        f"{settings.api_base_url}/v1/profile/avatar/{user.id}"
        if user.avatar_override
        else user.avatar
    )
    return SessionOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar=avatar,
        connected=connected,
        missing_scopes=missing,
        profile_complete=bool(profile and profile.headline and profile.bio),
        calendar_connected=has_calendar_scope(scopes),
        is_paid=user.is_paid,
        is_admin=user.is_admin,
    )


@router.post("/google", response_model=SessionOut)
async def sign_in_with_google(
    payload: GoogleSignIn,
    response: Response,
    settings: SettingsDep,
) -> SessionOut:
    try:
        identity = verify_id_token(payload.id_token, settings.google_client_id)
    except GoogleAuthError as exc:
        # A rejected sign-in is the single most opaque failure in this system -
        # the browser gets a generic error page and the reason lives here. The
        # message names the check that failed and never includes the token.
        logger.warning("google sign-in rejected: %s", exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    # Sign-in is the one flow that has to find a user before there is a session
    # to bind to. `find_user_id_by_google_sub` is a SECURITY DEFINER function
    # that returns an id and nothing else; everything after it runs under
    # normal row-level security, bound to that id. Ids are generated here
    # rather than by the database precisely so a brand-new user can be bound
    # before the row exists.
    async with SessionFactory() as session:
        found = await session.scalar(
            text("SELECT find_user_id_by_google_sub(:sub)"), {"sub": identity.sub}
        )
        user_id = found or uuid4()
        await bind_user(session, user_id)

        user = await session.scalar(select(User).where(User.id == user_id))
        if user is None:
            user = User(
                id=user_id,
                google_sub=identity.sub,
                email=identity.email,
                name=identity.name,
                avatar=identity.picture,
            )
            session.add(user)
            await session.flush()
            session.add(Profile(user_id=user.id))
        else:
            # Keep the display fields fresh, and clear a previous disconnect:
            # signing in again is how a revoked grant gets repaired.
            user.email = identity.email
            user.name = identity.name or user.name
            user.avatar = identity.picture or user.avatar
            user.disconnected_at = None
            user.disconnected_reason = ""

        if payload.refresh_token:
            blob = encrypt(
                payload.refresh_token,
                settings.master_key_bytes,
                aad=str(user.id).encode("ascii"),
            )
            existing = await session.scalar(
                select(GoogleToken).where(GoogleToken.user_id == user.id)
            )
            if existing is None:
                session.add(
                    GoogleToken(
                        user_id=user.id,
                        refresh_token_enc=blob,
                        scopes=payload.scopes,
                        expires_at=payload.expires_at,
                    )
                )
            else:
                existing.refresh_token_enc = blob
                existing.scopes = payload.scopes or existing.scopes
                existing.expires_at = payload.expires_at

        token_row = await session.scalar(select(GoogleToken).where(GoogleToken.user_id == user.id))
        profile = await session.scalar(select(Profile).where(Profile.user_id == user.id))
        await session.commit()

        if token_row is not None:
            await _arm_watch(session, user, settings)

        token, expires = issue_session(
            user.id, settings.session_secret, settings.session_ttl_minutes
        )
        response.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            secure=settings.environment != "development",
            samesite="lax",
            expires=expires,
            path="/",
        )
        scopes = payload.scopes or (token_row.scopes if token_row else [])
        return _session_out(
            user,
            settings,
            connected=token_row is not None,
            missing=missing_scopes(scopes),
            profile=profile,
            scopes=scopes,
        )


@router.get("/me", response_model=SessionOut)
async def me(user: CurrentUser, session: Db, settings: SettingsDep) -> SessionOut:
    token_row = await session.scalar(select(GoogleToken).where(GoogleToken.user_id == user.id))
    profile = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    return _session_out(
        user,
        settings,
        connected=token_row is not None and user.disconnected_at is None,
        missing=missing_scopes(token_row.scopes if token_row else []),
        profile=profile,
        scopes=token_row.scopes if token_row else [],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(user: CurrentUser, session: Db, response: Response) -> None:
    """Forget the Google grant. Stops all sending immediately."""
    await session.execute(delete(GoogleToken).where(GoogleToken.user_id == user.id))
    user.disconnected_at = datetime.now(timezone.utc)
    user.disconnected_reason = "disconnected by the user"
    await session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
