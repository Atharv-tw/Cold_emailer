"""Let an operator see accounts other than their own.

Revision ID: 0011
Revises: 0010

`users` has been under RLS since 0001, with one policy covering every command:

    id = nullif(current_setting('app.user_id', true), '')::uuid

Strictly self-only, which is right for every request the product makes and
wrong for the only one it now also has to make. The admin panel added in 0010
reads accounts across users, and under that predicate a session bound to the
operator sees exactly one row - their own. The symptom was a payments list that
came back empty while the claim sat in the table, because `list_payments` joins
to `users` and the join dropped every row the operator did not own.

An unbound session is not the escape hatch: the policy compares against a
setting that is then NULL, so it sees zero rows rather than all of them. That
is the design working.

So this adds two permissive policies gated on a second session setting.
Multiple permissive policies for the same command OR together, so the existing
isolation is untouched - each of these only ever adds rows, and only for a
session that has explicitly said it is acting as an operator:

    SELECT  self, or admin   - the panel can list accounts
    UPDATE  self, or admin   - the panel can grant and revoke pool access

INSERT and DELETE are deliberately not included. Nothing in the panel creates
or removes accounts, and a policy is easier to add later than to notice.

`app.is_admin` is set by the `AdminUser` dependency and nowhere else, only
after `is_admin` has been read off the operator's own row under the self
policy above. A request that never asks for an admin route never sets it, and
`current_setting(..., true)` returns NULL when unset, which fails closed.

The trigger is the other half. Widening UPDATE to every row would otherwise
mean the application role could write `is_admin`, and the whole premise of the
admin panel is that it cannot - there is no path from "signed in" to
"privileged". The check is scoped to the application role so the one-off
bootstrap, run as the owner, still works:

    UPDATE users SET is_admin = true WHERE email = '...';
"""
from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

APP_ROLE = "outreach_app"

_IS_ADMIN = "current_setting('app.is_admin', true) = 'on'"


def upgrade() -> None:
    op.execute(f"CREATE POLICY users_admin_read ON users FOR SELECT USING ({_IS_ADMIN})")
    op.execute(
        f"CREATE POLICY users_admin_write ON users FOR UPDATE "
        f"USING ({_IS_ADMIN}) WITH CHECK ({_IS_ADMIN})"
    )

    # RLS cannot express "this column did not change" - WITH CHECK only sees
    # the new row, never the old one - so the immutability of `is_admin` needs
    # a trigger rather than a policy.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION users_is_admin_is_immutable() RETURNS trigger AS $$
        BEGIN
            IF current_user = '{APP_ROLE}' AND NEW.is_admin IS DISTINCT FROM OLD.is_admin THEN
                RAISE EXCEPTION
                    'is_admin cannot be changed by the application role; set it in SQL as the owner';
            END IF;
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER users_is_admin_immutable "
        "BEFORE UPDATE ON users FOR EACH ROW "
        "EXECUTE FUNCTION users_is_admin_is_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS users_is_admin_immutable ON users")
    op.execute("DROP FUNCTION IF EXISTS users_is_admin_is_immutable()")
    op.execute("DROP POLICY IF EXISTS users_admin_write ON users")
    op.execute("DROP POLICY IF EXISTS users_admin_read ON users")
