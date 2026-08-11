"""Keep the reply that ended the sequence.

Revision ID: 0014
Revises: 0013

The classifier already fetches the inbound message and flattens it to text to
decide what it means, then threw the text away and kept the subject line in
`targets.status_detail`. So the product could tell you that someone answered
and never what they said - the one fact a person actually wants at that moment.
Storing it costs no additional Gmail call.

A separate table rather than columns on `targets`, because a reply body is
unbounded and `select(Target)` reads every column. On `targets` that text would
be dragged through the reconcile sweep, the target list and the pre-send
check - all hot, none of which read it. Postgres would move the larger values
out of line into TOAST storage, but the ORM still names the column in every
SELECT, so the reads would happen. Here they happen only when someone opens the
target.

`target_id` is the primary key, which caps this at one reply per target. That
is an invariant and not merely today's behaviour: replying is terminal, and a
finished sequence may only start a new cycle from a *silent* target, so a
target that answered cannot come round and answer again.

Row-level security matches every other user-scoped table, and 0002 set default
privileges for the application role, so no explicit GRANT is needed here.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

TABLE = "target_replies"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column(
            "target_id",
            UUID(as_uuid=True),
            sa.ForeignKey("targets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_email", sa.Text(), nullable=False, server_default=""),
        sa.Column("subject", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("gmail_message_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])

    # Partial, because the only question asked of this column at scale is "how
    # many are unread" for the dashboard badge. Indexing the read ones too
    # would be paying to find rows nothing looks for.
    op.create_index(
        f"ix_{TABLE}_unread", TABLE, ["user_id"], postgresql_where=sa.text("read_at IS NULL")
    )

    predicate = "user_id = nullif(current_setting('app.user_id', true), '')::uuid"
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    # Without FORCE the owning role silently bypasses its own policies.
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {TABLE}_isolation ON {TABLE} "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {TABLE}_isolation ON {TABLE}")
    op.drop_index(f"ix_{TABLE}_unread", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
    op.drop_table(TABLE)
