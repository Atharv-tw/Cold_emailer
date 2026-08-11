"""Record when a Gmail notification last actually arrived.

Revision ID: 0013
Revises: 0012

`gmail_watch` tracked only our side of the conversation: `last_checked_at` for
when we called `watch`, `expires_at` for what Gmail said in reply. Both are
about a request that succeeded, and neither can tell whether a single
notification ever came back.

That gap hid a real outage. After the move off Render the Pub/Sub subscription
still pointed at the old host and a route that does not exist in this codebase,
so every notification was delivered to a 404 and retried into nothing. The ops
page reported the watch healthy the whole time, because by its own definition
it was: Gmail had accepted the watch and the expiry was a week out. Reply
detection ran entirely on the reconcile sweep for weeks and nobody could have
known from inside the application.

Nullable with no backfill. NULL means "no notification since this column
existed", which is indistinguishable from a genuinely silent mailbox, so the
ops check pairs it with a live watch and a two-day grace before calling it a
fault. The first real notification fills it in.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gmail_watch",
        sa.Column("last_push_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gmail_watch", "last_push_at")
