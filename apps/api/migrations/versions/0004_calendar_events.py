"""Track the mirrored Google Calendar reminder on each scheduled follow-up.

Revision ID: 0004
Revises: 0003

Folded into 0001 — google_event_id and event_synced_due_at are created
with the schedule table. This migration is kept as a no-op to preserve
the revision chain.
"""
from __future__ import annotations

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
