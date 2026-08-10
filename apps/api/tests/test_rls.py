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

# The shared-pool row. Distinctive so the owner-connection cleanup cannot
# plausibly remove anything real.
POOL_EMAIL = "pool-contact@test.example"


def _dsn() -> str:
    # psycopg wants a plain libpq DSN, not SQLAlchemy's dialect prefix.
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")


def _owner_dsn() -> str:
    """The schema owner, which is what can write a row into the shared pool.

    `WITH CHECK` refuses any insert whose `owner_user_id` is not the bound
    user, and FORCE means being the table owner is not enough on its own -
    seeding the pool needs a role with BYPASSRLS. That is exactly the
    constraint the real loader runs under, so the test seeds the same way.
    """
    return get_settings().alembic_url.replace("postgresql+psycopg://", "postgresql://")


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
            # A private contact each: same address for both users, which is
            # legal and is the case a naive unique index would break.
            self.cursor.execute(
                "INSERT INTO contacts (id, owner_user_id, email) VALUES (%s, %s, %s)",
                (uuid.uuid4(), user_id, f"private-{sub}@example.com"),
            )

    def visible_targets(self) -> list[str]:
        self.cursor.execute("SELECT email FROM targets ORDER BY email")
        return [row[0] for row in self.cursor.fetchall()]

    def visible_private_contacts(self) -> list[str]:
        """Owned rows only.

        Deliberately not "every contact": the pool is shared and global, so a
        loaded database has hundreds of rows every user can legitimately see.
        A test that asserted on the whole table would be asserting on whatever
        happened to be seeded, which is not a property of RLS at all.
        """
        self.cursor.execute(
            "SELECT email FROM contacts WHERE owner_user_id IS NOT NULL ORDER BY email"
        )
        return [row[0] for row in self.cursor.fetchall()]

    def visible_contacts(self) -> list[str]:
        self.cursor.execute("SELECT email FROM contacts ORDER BY email")
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

    # -------------------------------------------------------------- contacts

    def test_contacts_has_rls_forced(self):
        """Not covered by the loop over USER_SCOPED_TABLES, which contacts is
        deliberately absent from - so it gets asserted on its own."""
        self.cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'contacts'"
        )
        enabled, forced = self.cursor.fetchone()
        self.assertTrue(enabled, "contacts does not have RLS enabled")
        self.assertTrue(forced, "contacts does not have RLS forced")

    def test_a_user_sees_only_their_own_private_contact(self):
        self.bind(ALICE)
        self.assertEqual(self.visible_private_contacts(), ["private-sub-a@example.com"])
        self.bind(BOB)
        self.assertEqual(self.visible_private_contacts(), ["private-sub-b@example.com"])

    def test_a_user_cannot_create_a_contact_in_the_shared_pool(self):
        """WITH CHECK omits the public case, so a request cannot write one."""
        import psycopg

        self.bind(ALICE)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.cursor.execute(
                "INSERT INTO contacts (id, owner_user_id, email) VALUES (%s, NULL, %s)",
                (uuid.uuid4(), "smuggled-into-the-pool@example.com"),
            )

    def test_a_user_cannot_create_a_contact_owned_by_someone_else(self):
        import psycopg

        self.bind(BOB)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.cursor.execute(
                "INSERT INTO contacts (id, owner_user_id, email) VALUES (%s, %s, %s)",
                (uuid.uuid4(), ALICE, "stolen@example.com"),
            )

    def test_a_user_cannot_move_their_contact_into_the_pool(self):
        """The UPDATE equivalent of the insert above: WITH CHECK applies to the
        new row too, so a private contact cannot be donated to everyone."""
        import psycopg

        self.bind(ALICE)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.cursor.execute("UPDATE contacts SET owner_user_id = NULL")

    def test_a_user_can_edit_their_own_private_contact(self):
        """The positive half. Without this the negative tests above would still
        pass under a policy so tight that nobody could edit anything."""
        self.bind(ALICE)
        self.cursor.execute(
            "UPDATE contacts SET name = 'Renamed' WHERE email = %s",
            ("private-sub-a@example.com",),
        )
        self.assertEqual(self.cursor.rowcount, 1)

    def test_a_user_can_delete_their_own_private_contact(self):
        self.bind(ALICE)
        self.cursor.execute(
            "DELETE FROM contacts WHERE email = %s", ("private-sub-a@example.com",)
        )
        self.assertEqual(self.cursor.rowcount, 1)

    def test_a_user_cannot_edit_another_users_private_contact(self):
        self.bind(BOB)
        self.cursor.execute(
            "UPDATE contacts SET name = 'tampered' WHERE email = %s",
            ("private-sub-a@example.com",),
        )
        self.assertEqual(self.cursor.rowcount, 0)

    def test_contacts_has_a_policy_for_every_command(self):
        """A single policy cannot express this table's rules: DELETE consults
        only USING, so anything readable would be deletable. Four commands,
        four policies - assert none has gone missing."""
        self.cursor.execute(
            "SELECT cmd FROM pg_policies WHERE tablename = 'contacts' ORDER BY cmd"
        )
        self.assertEqual(
            sorted(row[0] for row in self.cursor.fetchall()),
            ["DELETE", "INSERT", "SELECT", "UPDATE"],
        )

    def test_an_unbound_session_sees_no_contacts(self):
        """Neither private rows nor the pool. Equality is right here: the
        correct answer is genuinely nothing, however much is seeded."""
        self.bind(None)
        self.assertEqual(self.visible_contacts(), [])


@unittest.skipUnless(AVAILABLE, "no migrated database on DATABASE_URL")
class TestSharedPool(unittest.TestCase):
    """The public half of `contacts`, which needs a committed row to exist.

    A pool row cannot be seeded inside the app connection's transaction - the
    policy refuses it - so it is written by the owner connection and committed,
    then removed again. Everything else still rolls back.
    """

    owner_available = False

    @classmethod
    def setUpClass(cls):
        import psycopg

        try:
            with psycopg.connect(_owner_dsn(), connect_timeout=3) as connection:
                connection.autocommit = True
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM contacts WHERE email = %s", (POOL_EMAIL,))
                    cursor.execute(
                        "INSERT INTO contacts (id, owner_user_id, name, email, company) "
                        "VALUES (%s, NULL, %s, %s, %s)",
                        (uuid.uuid4(), "Pool Person", POOL_EMAIL, "Pool Co"),
                    )
            cls.owner_available = True
        except Exception:  # noqa: BLE001 - no BYPASSRLS role reachable
            cls.owner_available = False

    @classmethod
    def tearDownClass(cls):
        if not cls.owner_available:
            return
        import psycopg

        with psycopg.connect(_owner_dsn()) as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM contacts WHERE email = %s", (POOL_EMAIL,))

    def setUp(self):
        if not self.owner_available:
            self.skipTest("no BYPASSRLS role on MIGRATION_DATABASE_URL to seed the pool")
        import psycopg

        self.connection = psycopg.connect(_dsn())
        self.connection.autocommit = False
        self.cursor = self.connection.cursor()
        self.bind(ALICE)
        self.cursor.execute(
            "INSERT INTO users (id, google_sub, email) VALUES (%s, %s, %s)",
            (ALICE, "sub-pool-a", "pool-a@test.example"),
        )

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()

    def bind(self, user_id: uuid.UUID | None):
        self.cursor.execute(
            "SELECT set_config('app.user_id', %s, true)", (str(user_id) if user_id else "",)
        )

    def pool_rows(self) -> list[str]:
        """The seeded row only.

        Filtered rather than counted: a real database has the loaded pool in it
        too, and those rows are not what these tests are about.
        """
        self.cursor.execute(
            "SELECT email FROM contacts WHERE owner_user_id IS NULL AND email = %s",
            (POOL_EMAIL,),
        )
        return [row[0] for row in self.cursor.fetchall()]

    # ------------------------------------------------------------------ tests

    def test_every_bound_user_sees_the_pool(self):
        self.bind(ALICE)
        self.assertEqual(self.pool_rows(), [POOL_EMAIL])
        # A user with no row of their own still sees it - that is the point.
        self.bind(BOB)
        self.assertEqual(self.pool_rows(), [POOL_EMAIL])

    def test_a_user_cannot_update_a_pool_row(self):
        self.bind(ALICE)
        self.cursor.execute("UPDATE contacts SET name = 'tampered' WHERE email = %s", (POOL_EMAIL,))
        # Readable, so no error - but not writable, so nothing is touched.
        self.assertEqual(self.cursor.rowcount, 0)

    def test_a_user_cannot_delete_a_pool_row(self):
        self.bind(ALICE)
        self.cursor.execute("DELETE FROM contacts WHERE email = %s", (POOL_EMAIL,))
        self.assertEqual(self.cursor.rowcount, 0)

    def test_an_unbound_session_cannot_read_the_pool(self):
        """`owner_user_id IS NULL` is true whatever the session, so without the
        bound-user term in USING, a forgotten filter would leak the whole pool.
        This is the test that catches that regression."""
        self.bind(None)
        self.assertEqual(self.pool_rows(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
