"""Request-scoped dependencies: who is calling, and a session bound to them."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import bind_user, get_session
from .models import User
from .security import COOKIE_NAME, SessionError, read_session
from .settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _token_from(cookie: str | None, authorization: str | None) -> str:
    if cookie:
        return cookie
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")


async def current_user_id(
    settings: SettingsDep,
    session_cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    token = _token_from(session_cookie, authorization)
    try:
        return read_session(token, settings.session_secret)
    except SessionError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


async def db(
    user_id: Annotated[uuid.UUID, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncSession:
    """A session bound to the caller, so RLS applies for the whole request."""
    await bind_user(session, user_id)
    return session


async def current_user(
    user_id: Annotated[uuid.UUID, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(db)],
) -> User:
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        # The session token outlived the account it names.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account no longer exists")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
CurrentUserId = Annotated[uuid.UUID, Depends(current_user_id)]
Db = Annotated[AsyncSession, Depends(db)]


async def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    """The operator, for routes that act across accounts.

    `is_admin` is set by hand in SQL and by nothing else - no handler anywhere
    accepts it in a payload - so this reads a column the request could not have
    influenced. That is the whole guarantee: there is no path from "signed in"
    to "privileged", and a bug in an admin route therefore cannot create one.

    403 rather than 404: hiding that the routes exist would only obscure them
    from someone already authenticated, and an honest refusal is easier to
    debug than a lie.
    """
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not an admin")
    return user


AdminUser = Annotated[User, Depends(admin_user)]


async def gemini_api_key(
    x_gemini_api_key: Annotated[str | None, Header(alias="X-Gemini-Api-Key")] = None,
) -> str:
    """Every AI call is billed to the user's own key, not a server one.

    There is no server-side fallback: a missing key is a 422 the caller can
    act on, not a silent use of someone else's quota.
    """
    if not x_gemini_api_key or not x_gemini_api_key.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Add your Gemini API key in Settings to use AI features.",
        )
    return x_gemini_api_key.strip()


GeminiKey = Annotated[str, Depends(gemini_api_key)]
