"""A contact catalogue - shared pool plus private rows - and dead addresses.

Revision ID: 0008
Revises: 0007

`targets` conflated two things: who a person is, and what one user has done
about them. This splits the first out into `contacts`, where a row is either
in the shared pool (`owner_user_id IS NULL`) or private to one user.

The split is additive on purpose. `targets` keeps every person column it had,
now as a snapshot copied at creation rather than the only copy. That is what
lets this migration ship without touching the eight modules that read
`target.name`, `target.company` and friends - and it is independently right,
because a target should record what was actually sent even if the catalogue
entry is corrected afterwards.

Two things here are easy to get wrong and are handled explicitly:

* **RLS.** The uniform policy the other tables share is
  `user_id = current_setting('app.user_id')`. A pool contact's owner is NULL,
  and `NULL = <uuid>` is false, so under that predicate the whole pool would be
  invisible to every user - no error, just an empty list. `contacts` gets an
  asymmetric policy: `USING` admits public rows, `WITH CHECK` refuses them.
* **NULLs in unique constraints.** Postgres treats them as distinct, so
  `UNIQUE (owner_user_id, email)` does not dedupe the pool - every public row
  has a NULL owner and so never collides. The partial index below does that.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


# Readable if public or owned; writable only if owned. The asymmetry is the
# whole mechanism: a request can see the pool and can never write into it.
#
# Which means the pool loader cannot use the application's connection. Under
# FORCE even the table owner is subject to this policy, so seeding needs a role
# with BYPASSRLS. On Neon that is `neondb_owner`; there is no superuser to fall
# back on. Verified against production: `outreach_app` inserting a row with a
# NULL owner raises InsufficientPrivilege, which is the intended behaviour and
# the reason the loader takes its own DSN.
#
# `_BOUND` is not redundant. Without it `owner_user_id IS NULL` is true whatever
# the session is, so an *unbound* connection - one where the request forgot to
# announce its user - would read the entire pool. Every other table in this
# schema fails closed when unbound, and a pool that may later sit behind a
# paywall is the last thing that should be the exception.
_BOUND = "nullif(current_setting('app.user_id', true), '') IS NOT NULL"
_OWNED = "owner_user_id = nullif(current_setting('app.user_id', true), '')::uuid"
_READABLE = f"({_BOUND} AND ({_OWNED} OR owner_user_id IS NULL))"


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(255), nullable=False, server_default=""),
        sa.Column("links", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("company", sa.String(255), nullable=False, server_default=""),
        sa.Column("company_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("company_website", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("company_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(64), nullable=False, server_default=""),
        sa.Column("verification", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("source_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("owner_user_id", "email", name="uq_contacts_owner_email"),
    )

    # Dedupes the pool, which the constraint above cannot: every public row has
    # a NULL owner and NULLs never collide in a unique constraint.
    op.execute(
        "CREATE UNIQUE INDEX uq_contacts_public_email "
        "ON contacts (email) WHERE owner_user_id IS NULL"
    )

    # Re-running a loader updates rather than duplicating. Partial, because
    # user-created contacts share the empty-string default.
    op.execute(
        "CREATE UNIQUE INDEX uq_contacts_source_id "
        "ON contacts (source_id) WHERE source_id <> ''"
    )

    # Listing the pool is an anti-join against dead_addresses on `email`.
    op.create_index("ix_contacts_email", "contacts", ["email"])

    op.create_table(
        "dead_addresses",
        sa.Column("email", sa.String(320), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.add_column(
        "targets",
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            # SET NULL, not CASCADE: retiring a catalogue entry must not delete
            # a user's sent thread along with it.
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_targets_contact_id", "targets", ["contact_id"])
    op.add_column(
        "targets",
        sa.Column("cycles_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("targets", sa.Column("last_cycle_ended_at", sa.DateTime(timezone=True)))

    # Every existing target becomes a private contact owned by its user, and
    # points at it. Done in SQL rather than by loading the ORM so it does not
    # depend on the models still looking like this in a year.
    #
    # DISTINCT ON collapses the case where a user somehow holds two rows for one
    # address; uq_targets_user_email should make that impossible, but a backfill
    # that assumes its own invariants is how a migration fails at 3am.
    op.execute(
        """
        INSERT INTO contacts (
            id, owner_user_id, name, email, role, links,
            company, target_type, company_type, timezone, verification
        )
        SELECT DISTINCT ON (t.user_id, t.email)
            gen_random_uuid(), t.user_id, t.name, t.email, t.role, t.links,
            t.company, t.target_type, t.company_type, t.timezone, t.verification
        FROM targets t
        ORDER BY t.user_id, t.email, t.created_at
        """
    )
    op.execute(
        """
        UPDATE targets t
        SET contact_id = c.id
        FROM contacts c
        WHERE c.owner_user_id = t.user_id AND c.email = t.email
        """
    )

    # Added after the backfill: before it, every target has a NULL contact_id,
    # and NULLs are distinct so the constraint would have been satisfied but
    # meaningless. Afterwards it is real.
    op.create_unique_constraint(
        "uq_targets_user_contact", "targets", ["user_id", "contact_id"]
    )

    op.execute("ALTER TABLE contacts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE contacts FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY contacts_isolation ON contacts "
        f"USING ({_READABLE}) WITH CHECK ({_OWNED})"
    )

    # dead_addresses belongs to no user and carries nothing private: it says a
    # mailbox bounced, nothing about who wrote to it. No RLS, same as
    # recipient_guard and worker_heartbeat.


def downgrade() -> None:
    # Nothing to copy back - `targets` never gave its person columns up, which
    # is the point of the split being additive.
    op.execute("DROP POLICY IF EXISTS contacts_isolation ON contacts")
    op.drop_constraint("uq_targets_user_contact", "targets", type_="unique")
    op.drop_column("targets", "last_cycle_ended_at")
    op.drop_column("targets", "cycles_used")
    op.drop_index("ix_targets_contact_id", table_name="targets")
    op.drop_column("targets", "contact_id")
    op.drop_table("dead_addresses")
    op.drop_index("ix_contacts_email", table_name="contacts")
    op.execute("DROP INDEX IF EXISTS uq_contacts_source_id")
    op.execute("DROP INDEX IF EXISTS uq_contacts_public_email")
    op.drop_table("contacts")
