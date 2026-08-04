"""Track the mirrored Google Calendar reminder on each scheduled follow-up.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schedule",
        sa.Column("google_event_id", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "schedule",
        sa.Column("event_synced_due_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schedule", "event_synced_due_at")
    op.drop_column("schedule", "google_event_id")
