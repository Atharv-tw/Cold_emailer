"""Row-level security, against a real database.

This file exists because 190 passing tests did not notice that RLS was doing
nothing at all. The policies were correct and every table had FORCE ROW LEVEL
SECURITY set - but the application connected as a superuser, and superusers
bypass RLS outright. Bound to one user, a connection could read every other
user's targets and insert rows owned by them.

No amount of mocking would have caught that. It is a property of the live
connection's role, so it gets tested against a live connection or not at all.

Skipped when there is no database. Run it with:

    docker compose -f infra/docker-compose.yml up -d
    cd apps/api && alembic upgrade head
    python -m unittest discover -s apps/api/tests
"""

from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from app.settings import get_settings  # noqa: E402

ALICE = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
BOB = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")


def _dsn() -> str:
    # psycopg wants a plain libpq DSN, not SQLAlchemy's dialect prefix.
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")


def _database_available() -> bool:
    try:
        import psycopg

        with psycopg.connect(_dsn(), connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM targets LIMIT 0")
        return True
    except Exception:  # noqa: BLE001 - any failure means "cannot run these"
        return False


AVAILABLE = _database_available()


@unittest.skipUnless(AVAILABLE, "no migrated database on DATABASE_URL")
class TestRowLevelSecurity(unittest.TestCase):
    """Every test runs in a transaction that is rolled back."""

    def setUp(self):
        import psycopg

        self.connection = psycopg.connect(_dsn())
        self.connection.autocommit = False
        self.cursor = self.connection.cursor()
        self._seed()

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()

    def bind(self, user_id: uuid.UUID | None):
        self.cursor.execute(
            "SELECT set_config('app.user_id', %s, true)", (str(user_id) if user_id else "",)
        )

    def _seed(self):
        for user_id, sub, email, target in (
            (ALICE, "sub-a", "a@test.example", "alex@example.com"),
            (BOB, "sub-b", "b@test.example", "dana@example.com"),
        ):
            self.bind(user_id)
            self.cursor.execute(
                "INSERT INTO users (id, google_sub, email) VALUES (%s, %s, %s)",
                (user_id, sub, email),
            )
            self.cursor.execute(
                "INSERT INTO targets (id, user_id, email) VALUES (%s, %s, %s)",
                (uuid.uuid4(), user_id, target),
            )

    def visible_targets(self) -> list[str]:
        self.cursor.execute("SELECT email FROM targets ORDER BY email")
        return [row[0] for row in self.cursor.fetchall()]

    # ------------------------------------------------------------------ tests

    def test_the_connection_is_not_a_superuser(self):
        """The whole mechanism rests on this, so assert it directly."""
        self.cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        is_superuser, bypasses_rls = self.cursor.fetchone()
        self.assertFalse(is_superuser, "the app is connecting as a superuser - RLS is a no-op")
        self.assertFalse(bypasses_rls, "the app's role has BYPASSRLS - RLS is a no-op")

    def test_a_user_sees_only_their_own_targets(self):
        self.bind(BOB)
        self.assertEqual(self.visible_targets(), ["dana@example.com"])
        self.bind(ALICE)
        self.assertEqual(self.visible_targets(), ["alex@example.com"])

    def test_a_user_sees_only_their_own_account(self):
        self.bind(BOB)
        self.cursor.execute("SELECT email FROM users")
        self.assertEqual([row[0] for row in self.cursor.fetchall()], ["b@test.example"])

    def test_a_user_cannot_write_a_row_owned_by_someone_else(self):
        import psycopg

        self.bind(BOB)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.cursor.execute(
                "INSERT INTO targets (id, user_id, email) VALUES (%s, %s, %s)",
                (uuid.uuid4(), ALICE, "stolen@example.com"),
            )

    def test_a_user_cannot_update_another_users_row(self):
        self.bind(ALICE)
        self.cursor.execute("SELECT id FROM targets")
        alices_target = self.cursor.fetchone()[0]

        self.bind(BOB)
        self.cursor.execute(
            "UPDATE targets SET hook = 'tampered' WHERE id = %s", (alices_target,)
        )
        # Not an error - the row is simply not visible to update.
        self.assertEqual(self.cursor.rowcount, 0)

    def test_an_unbound_session_sees_nothing(self):
        """Fails closed. A forgotten filter returns empty, not everybody."""
        self.bind(None)
        self.assertEqual(self.visible_targets(), [])
        self.cursor.execute("SELECT count(*) FROM users")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_an_unbound_session_does_not_error(self):
        # nullif(..., '')::uuid rather than ''::uuid, so an unbound session
        # returns no rows instead of raising on every query.
        self.bind(None)
        self.cursor.execute("SELECT count(*) FROM messages")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_sign_in_lookup_works_without_a_bound_user(self):
        """The one deliberate exemption, and it returns an id and nothing else."""
        self.bind(None)
        self.cursor.execute("SELECT find_user_id_by_google_sub('sub-a')")
        self.assertEqual(self.cursor.fetchone()[0], ALICE)

    def test_the_application_cannot_drop_its_own_policies(self):
        import psycopg

        self.bind(ALICE)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.cursor.execute("DROP POLICY targets_isolation ON targets")

    def test_the_application_cannot_alter_the_schema(self):
        import psycopg

        self.bind(ALICE)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.cursor.execute("ALTER TABLE targets DISABLE ROW LEVEL SECURITY")

    def test_every_user_scoped_table_has_rls_forced(self):
        from app.models import USER_SCOPED_TABLES

        self.cursor.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
            """,
            (list(USER_SCOPED_TABLES) + ["users"],),
        )
        rows = self.cursor.fetchall()
        self.assertEqual(len(rows), len(USER_SCOPED_TABLES) + 1)
        for name, enabled, forced in rows:
            self.assertTrue(enabled, f"{name} does not have RLS enabled")
            # Without FORCE, the owning role silently bypasses its own policies.
            self.assertTrue(forced, f"{name} does not have RLS forced")

    def test_the_touch_ceiling_is_enforced_by_the_database(self):
        import psycopg

        self.bind(ALICE)
        self.cursor.execute("SELECT id FROM targets")
        target_id = self.cursor.fetchone()[0]
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.cursor.execute(
                "UPDATE targets SET touches_sent = 4 WHERE id = %s", (target_id,)
            )

    def test_the_daily_cap_cannot_be_raised_past_the_ceiling(self):
        import psycopg

        self.bind(ALICE)
        self.cursor.execute(
            "INSERT INTO profiles (user_id, daily_cap) VALUES (%s, %s)", (ALICE, 20)
        )
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.cursor.execute(
                "UPDATE profiles SET daily_cap = 5000 WHERE user_id = %s", (ALICE,)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
