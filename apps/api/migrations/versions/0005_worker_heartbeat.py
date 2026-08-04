"""A heartbeat row the worker touches each run.

Deliberately not user-scoped and outside row-level security: it holds only a
job name and a timestamp, so any request may read whether the worker is alive.

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeat",
        sa.Column("job", sa.String(length=64), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeat")
