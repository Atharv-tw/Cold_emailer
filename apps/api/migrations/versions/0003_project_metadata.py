"""Add profile project matching metadata.

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profile_projects",
        sa.Column("categories", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "profile_projects",
        sa.Column("best_for", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("profile_projects", "best_for")
    op.drop_column("profile_projects", "categories")
