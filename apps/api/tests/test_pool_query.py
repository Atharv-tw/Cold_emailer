"""What the shared pool offers a user, against a real database.

The exclusions are the whole point of the listing query, and every one of them
fails silently if it is wrong: a dead address simply reappears in the browse
page and the next student spends their own Gmail reputation proving it is dead
again. So they get tested against Postgres rather than a mock - the JSONB
operator and the two anti-joins have no meaning anywhere else.

Skipped when there is no database. Run it with:

    docker compose -f infra/docker-compose.yml up -d
    cd apps/api && alembic upgrade head
"""

from __future__ import annotations

import asyncio
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.models import Contact, DeadAddress, Target, User  # noqa: E402
from app.routers.pool import pool_query  # noqa: E402
from app.settings import get_settings  # noqa: E402

ALICE = uuid.UUID("aaaaaaaa-1111-0000-0000-000000000001")


def _database_available() -> bool:
    try:
        import psycopg

        dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(dsn, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM contacts LIMIT 0")
        return True
    except Exception:  # noqa: BLE001
        return False


AVAILABLE = _database_available()


@unittest.skipUnless(AVAILABLE, "no migrated database on DATABASE_URL")
class TestPoolQuery(unittest.TestCase):
    """Each test builds its own pool inside a transaction that is rolled back.

    Pool rows need a session that bypasses RLS to write, so the fixtures go in
    through the owner connection - the same role the loader uses.
    """

    def setUp(self):
        self.engine = create_async_engine(get_settings().alembic_url, poolclass=None)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    def tearDown(self):
        asyncio.run(self.engine.dispose())

    def run_case(self, body):
        async def wrapped():
            async with self.sessions() as session:
                # The owner bypasses RLS, so `app.user_id` is not consulted -
                # but set it anyway so the query under test runs the same shape
                # it will in a request.
                await session.execute(
                    text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(ALICE)}
                )
                session.add(User(id=ALICE, google_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4()}@t.example"))
                await session.flush()
                try:
                    return await body(session)
                finally:
                    await session.rollback()

        return asyncio.run(wrapped())

    async def _emails(self, session, **kwargs) -> list[str]:
        rows = await session.scalars(pool_query(ALICE, **kwargs))
        return sorted(row.email for row in rows)

    def add_pool_contact(self, session, email: str, **overrides) -> Contact:
        contact = Contact(
            owner_user_id=None,
            name=overrides.pop("name", "Pool Person"),
            email=email,
            company=overrides.pop("company", "Pool Co"),
            target_type=overrides.pop("target_type", "founder"),
            company_type=overrides.pop("company_type", "ai"),
            verification=overrides.pop("verification", {"state": "unknown"}),
            **overrides,
        )
        session.add(contact)
        return contact

    # ------------------------------------------------------------------ tests

    def test_a_healthy_pool_contact_is_offered(self):
        async def body(session):
            self.add_pool_contact(session, "healthy@example.com")
            await session.flush()
            return await self._emails(session)

        self.assertIn("healthy@example.com", self.run_case(body))

    def test_a_private_contact_is_not_in_the_pool(self):
        async def body(session):
            session.add(Contact(owner_user_id=ALICE, email="mine@example.com"))
            await session.flush()
            return await self._emails(session)

        self.assertNotIn("mine@example.com", self.run_case(body))

    def test_a_retired_contact_is_withdrawn(self):
        from datetime import datetime, timezone

        async def body(session):
            self.add_pool_contact(
                session, "retired@example.com", retired_at=datetime.now(timezone.utc)
            )
            await session.flush()
            return await self._emails(session)

        self.assertNotIn("retired@example.com", self.run_case(body))

    def test_an_undeliverable_contact_is_hidden(self):
        """The loader's MX pass marks these; nobody should be offered one."""

        async def body(session):
            self.add_pool_contact(
                session,
                "nomx@example.com",
                verification={"state": "undeliverable", "reason": "no_mx"},
            )
            await session.flush()
            return await self._emails(session)

        self.assertNotIn("nomx@example.com", self.run_case(body))

    def test_a_risky_contact_is_still_offered(self):
        """`risky` is a warning, not a verdict - a domain mismatch is often a
        real address, and dropping them would discard 88 of 499."""

        async def body(session):
            self.add_pool_contact(
                session,
                "risky@example.com",
                verification={"state": "risky", "reason": "domain_mismatch"},
            )
            await session.flush()
            return await self._emails(session)

        self.assertIn("risky@example.com", self.run_case(body))

    def test_a_dead_address_is_hidden_from_everyone(self):
        async def body(session):
            self.add_pool_contact(session, "dead@example.com")
            session.add(DeadAddress(email="dead@example.com", reason="5.1.1"))
            await session.flush()
            return await self._emails(session)

        self.assertNotIn("dead@example.com", self.run_case(body))

    def test_someone_already_on_the_users_list_is_not_offered_again(self):
        async def body(session):
            self.add_pool_contact(session, "taken@example.com")
            session.add(Target(user_id=ALICE, email="taken@example.com"))
            await session.flush()
            return await self._emails(session)

        self.assertNotIn("taken@example.com", self.run_case(body))

    def test_facets_narrow_the_list(self):
        async def body(session):
            self.add_pool_contact(session, "founder@example.com", target_type="founder")
            self.add_pool_contact(session, "hr@example.com", target_type="hiring_manager")
            await session.flush()
            return await self._emails(session, target_type="hiring_manager")

        result = self.run_case(body)
        self.assertIn("hr@example.com", result)
        self.assertNotIn("founder@example.com", result)

    def test_search_matches_company_and_escapes_wildcards(self):
        async def body(session):
            self.add_pool_contact(session, "a@example.com", company="Aztech")
            self.add_pool_contact(session, "b@example.com", company="Beta")
            matched = await self._emails(session, q="Aztech")
            # A literal % must not behave as a wildcard and match everything.
            wildcard = await self._emails(session, q="%")
            return matched, wildcard

        matched, wildcard = self.run_case(body)
        self.assertIn("a@example.com", matched)
        self.assertNotIn("b@example.com", matched)
        self.assertEqual(wildcard, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
