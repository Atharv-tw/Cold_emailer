"""Add profile project matching metadata.

Revision ID: 0003
Revises: 0002

Folded into 0001 — categories and best_for are created with the table.
This migration is kept as a no-op to preserve the revision chain.
"""
from __future__ import annotations

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
