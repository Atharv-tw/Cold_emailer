"""Add trackers.

Revision ID: 0016
Revises: 0015
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

predicate = "user_id = nullif(current_setting('app.user_id', true), '')::uuid"


def upgrade() -> None:
    # tracked_threads
    op.create_table(
        "tracked_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gmail_thread_id", sa.String(64), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tracked_threads_user_id", "tracked_threads", ["user_id"])
    op.create_index("ix_tracked_threads_gmail_thread_id", "tracked_threads", ["gmail_thread_id"])
    op.create_index("ix_tracked_threads_status", "tracked_threads", ["status"])

    op.execute("ALTER TABLE tracked_threads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tracked_threads FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tracked_threads_isolation ON tracked_threads "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )

    # tracked_senders
    op.create_table(
        "tracked_senders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "email", name="uq_tracked_senders_user_email")
    )
    op.create_index("ix_tracked_senders_user_id", "tracked_senders", ["user_id"])
    op.create_index("ix_tracked_senders_status", "tracked_senders", ["status"])

    op.execute("ALTER TABLE tracked_senders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tracked_senders FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tracked_senders_isolation ON tracked_senders "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tracked_senders_isolation ON tracked_senders")
    op.drop_index("ix_tracked_senders_status", table_name="tracked_senders")
    op.drop_index("ix_tracked_senders_user_id", table_name="tracked_senders")
    op.drop_table("tracked_senders")

    op.execute("DROP POLICY IF EXISTS tracked_threads_isolation ON tracked_threads")
    op.drop_index("ix_tracked_threads_status", table_name="tracked_threads")
    op.drop_index("ix_tracked_threads_gmail_thread_id", table_name="tracked_threads")
    op.drop_index("ix_tracked_threads_user_id", table_name="tracked_threads")
    op.drop_table("tracked_threads")
