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
