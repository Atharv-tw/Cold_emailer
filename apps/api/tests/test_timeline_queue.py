"""What the target page is entitled to call "queued".

A pending schedule row is a slot, not a message. The worker looks for a draft
for that step and skips the row when there is none, so a row on its own sends
nothing - and the target page saying "Queued for Thursday - this is what goes
out" above an empty body promised a send that then silently never happened.

Skipped when there is no database. Run it with:

    docker compose -f infra/docker-compose.yml up -d
    cd apps/api && alembic upgrade head
"""

from __future__ import annotations

import asyncio
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.models import Message, ScheduleRow, Target, User  # noqa: E402
from app.routers.dashboard import timeline  # noqa: E402
from app.settings import get_settings  # noqa: E402


def _database_available() -> bool:
    try:
        import psycopg

        dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(dsn, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM schedule LIMIT 0")
        return True
    except Exception:  # noqa: BLE001
        return False


AVAILABLE = _database_available()


@unittest.skipUnless(AVAILABLE, "no migrated database on DATABASE_URL")
class TestQueuedFor(unittest.TestCase):
    def setUp(self):
        self.engine = create_async_engine(get_settings().alembic_url, poolclass=None)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.due = datetime.now(timezone.utc) + timedelta(days=3)

    def tearDown(self):
        asyncio.run(self.engine.dispose())

    def run_case(self, *, drafted: bool, state: str = "pending"):
        """Build one target with a pending step, optionally with a draft."""

        async def body():
            async with self.sessions() as session:
                user_id = uuid.uuid4()
                await session.execute(
                    text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
                )
                user = User(
                    id=user_id,
                    google_sub=f"sub-{user_id}",
                    email=f"{user_id}@test.example",
                )
                session.add(user)
                await session.flush()
                target = Target(user_id=user_id, email=f"t-{user_id}@example.com", touches_sent=1)
                session.add(target)
                await session.flush()

                session.add(
                    ScheduleRow(
                        user_id=user_id,
                        target_id=target.id,
                        step=2,
                        due_at=self.due,
                        state=state,
                    )
                )
                if drafted:
                    session.add(
                        Message(
                            user_id=user_id,
                            target_id=target.id,
                            step=2,
                            subject="Following up",
                            body="Body text",
                            status="draft",
                        )
                    )
                await session.flush()

                try:
                    return await timeline(target.id, user, session)
                finally:
                    await session.rollback()

        return asyncio.run(body())

    # ------------------------------------------------------------------ tests

    def test_a_written_draft_on_a_pending_step_is_queued(self):
        detail = self.run_case(drafted=True)
        self.assertIsNotNone(detail.queued_for)
        self.assertEqual(detail.queued_step, 2)

    def test_a_pending_step_with_nothing_written_is_not_queued(self):
        """The reported bug. After touch 1 sends, `_close_or_advance` opens a
        row for touch 2 immediately - long before anybody writes it."""
        detail = self.run_case(drafted=False)
        self.assertIsNone(detail.queued_for)
        self.assertIsNone(detail.queued_step)

    def test_a_cancelled_row_is_not_queued_even_with_a_draft(self):
        detail = self.run_case(drafted=True, state="cancelled")
        self.assertIsNone(detail.queued_for)

    def test_a_sent_message_does_not_keep_the_step_queued(self):
        """Only a `draft` counts. A step whose message already went out must not
        reappear as queued because its schedule row was left pending."""

        async def body():
            async with self.sessions() as session:
                user_id = uuid.uuid4()
                await session.execute(
                    text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
                )
                session.add(
                    User(id=user_id, google_sub=f"sub-{user_id}", email=f"{user_id}@t.example")
                )
                await session.flush()
                target = Target(user_id=user_id, email=f"s-{user_id}@example.com")
                session.add(target)
                await session.flush()
                session.add(
                    ScheduleRow(
                        user_id=user_id, target_id=target.id, step=1,
                        due_at=self.due, state="pending",
                    )
                )
                session.add(
                    Message(
                        user_id=user_id, target_id=target.id, step=1,
                        subject="Hi", body="Sent already", status="sent",
                    )
                )
                await session.flush()
                try:
                    return await timeline(target.id, await session.get(User, user_id), session)
                finally:
                    await session.rollback()

        detail = asyncio.run(body())
        self.assertIsNone(detail.queued_for)


if __name__ == "__main__":
    unittest.main(verbosity=2)
