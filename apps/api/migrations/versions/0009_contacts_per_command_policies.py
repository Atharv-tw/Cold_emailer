"""Split the contacts policy per command, so the pool cannot be deleted.

Revision ID: 0009
Revises: 0008

0008 gave `contacts` a single policy: `USING` admitted public rows so everyone
could read the pool, `WITH CHECK` refused them so nobody could write one. That
is right for INSERT and UPDATE and **wrong for DELETE**, because Postgres never
applies `WITH CHECK` to a DELETE - only `USING`. A pool row was therefore
readable, and so deletable, by any bound user. One request could empty the
shared pool for everybody.

Caught by `test_a_user_cannot_delete_a_pool_row`, which found rowcount 1.

The fix is four policies instead of one, so read and write get different
predicates rather than one predicate trying to serve both:

    SELECT  bound, and owned or public   - everyone reads the pool
    INSERT  owned                        - nobody writes into the pool
    UPDATE  owned                        - a pool row is not visible to update
    DELETE  owned                        - nor to delete

Multiple permissive policies for the same command OR together; these are for
different commands, so each stands alone. UPDATE and DELETE now match zero rows
on a pool entry rather than raising, which is the same shape as every other
table here: another user's row is simply not there.
"""
from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


_BOUND = "nullif(current_setting('app.user_id', true), '') IS NOT NULL"
_OWNED = "owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid"
# The bound check is not redundant: `owner_user_id IS NULL` is true whatever the
# session, so without it an unbound connection would read the entire pool.
_READABLE = f"({_BOUND} AND ({_OWNED} OR owner_user_id IS NULL))"


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS contacts_isolation ON contacts")

    op.execute(f"CREATE POLICY contacts_select ON contacts FOR SELECT USING ({_READABLE})")
    op.execute(f"CREATE POLICY contacts_insert ON contacts FOR INSERT WITH CHECK ({_OWNED})")
    op.execute(
        f"CREATE POLICY contacts_update ON contacts FOR UPDATE "
        f"USING ({_OWNED}) WITH CHECK ({_OWNED})"
    )
    op.execute(f"CREATE POLICY contacts_delete ON contacts FOR DELETE USING ({_OWNED})")


def downgrade() -> None:
    for name in ("contacts_select", "contacts_insert", "contacts_update", "contacts_delete"):
        op.execute(f"DROP POLICY IF EXISTS {name} ON contacts")

    op.execute(
        f"CREATE POLICY contacts_isolation ON contacts "
        f"USING ({_READABLE}) WITH CHECK ({_OWNED})"
    )
