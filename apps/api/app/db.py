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

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session as SyncSession

from .settings import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


_BOUND_USER = "app.user_id"
_ANNOUNCE = text("SELECT set_config('app.user_id', :uid, true)")

# Set only by the AdminUser dependency, only after `is_admin` has been read off
# the caller's own row. It widens the `users` policies added in 0011 so an
# operator can see accounts other than their own; every other session leaves it
# unset, and `current_setting(..., true)` is NULL then, which fails closed.
_BOUND_ADMIN = "app.is_admin"
_ANNOUNCE_ADMIN = text("SELECT set_config('app.is_admin', :flag, true)")


@event.listens_for(SyncSession, "after_begin")
def _announce_on_every_transaction(session, transaction, connection) -> None:
    """Re-announce the bound user whenever a new transaction opens.

    SET LOCAL dies with the transaction that set it. Binding once per request
    therefore only covered the first one, and every endpoint that commits and
    then reads - which is most of the write endpoints - carried on over a
    connection that had forgotten who it was acting for.

    The failure was not a leak, because RLS fails closed: the caller's own
    rows became invisible to them. But invisible reads as absent, and code
    that reacts to an absent row by creating it is then refused by the same
    policy, so it surfaced as a 500 rather than as anything about identity.

    Keeping the id in `session.info` makes the binding a property of the
    session rather than of one transaction, which is what the callers already
    assumed it was.
    """
    uid = session.info.get(_BOUND_USER)
    if uid is None:
        return  # never bound: an unbound session must keep seeing nothing
    connection.execute(_ANNOUNCE, {"uid": uid})

    # Same reasoning, same failure. An admin route that commits and then reads
    # - `set_plan` refreshes the row it just wrote - would otherwise carry on
    # over a connection that had forgotten the caller is an operator, and the
    # row it just updated would read back as absent.
    if session.info.get(_BOUND_ADMIN):
        connection.execute(_ANNOUNCE_ADMIN, {"flag": "on"})


async def bind_user(session: AsyncSession, user_id: uuid.UUID | None) -> None:
    """Tell Postgres who this session is acting for.

    The id goes through a bind parameter rather than string formatting -
    `set_config` exists precisely because `SET LOCAL` cannot be parameterised.
    It is still SET LOCAL, so nothing leaks into the next checkout of a pooled
    connection; `_announce_on_every_transaction` re-applies it after each
    commit.
    """
    uid = str(user_id) if user_id else ""
    # Recorded before the statement runs, so that if this call is what opens
    # the transaction, the listener already has an id to announce.
    session.sync_session.info[_BOUND_USER] = uid
    await session.execute(_ANNOUNCE, {"uid": uid})


async def elevate_admin(session: AsyncSession) -> None:
    """Let this session read and update accounts other than its own.

    Called by the `AdminUser` dependency and by nothing else, and only after
    `is_admin` has been read off the caller's own row - which is itself only
    readable under the self policy, so the flag can never be claimed by a
    request that did not already prove it.

    Recorded in `session.info` for the same reason the user id is: SET LOCAL
    dies with its transaction, and admin routes commit and then read.
    """
    session.sync_session.info[_BOUND_ADMIN] = True
    await session.execute(_ANNOUNCE_ADMIN, {"flag": "on"})


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
