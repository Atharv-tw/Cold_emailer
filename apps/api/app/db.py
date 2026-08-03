"""Database engine, sessions, and the row-level-security handshake.

Every request-scoped session announces which user it is acting for by setting
`app.user_id` on the connection, which is what the RLS policies compare
against. A session that never sets it sees nothing, so a code path that
forgets returns empty rather than returning everybody's.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .settings import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def bind_user(session: AsyncSession, user_id: uuid.UUID | None) -> None:
    """Tell Postgres who this transaction is for.

    SET LOCAL is scoped to the transaction, so the value cannot leak into the
    next checkout of a pooled connection. The id goes through a bind parameter
    rather than string formatting - `set_config` exists precisely because
    `SET LOCAL` cannot be parameterised.
    """
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id) if user_id else ""},
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


@asynccontextmanager
async def session_for(user_id: uuid.UUID | None) -> AsyncIterator[AsyncSession]:
    """A session already bound to a user. Used by the worker and cron jobs."""
    async with SessionFactory() as session:
        await bind_user(session, user_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
