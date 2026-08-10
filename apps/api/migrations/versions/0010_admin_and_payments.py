"""Paid access to the pool, an operator role, and the queue of payment claims.

Revision ID: 0010
Revises: 0009

Three things, all in service of charging for the contact pool.

`users.is_paid` is the entitlement. It is deliberately not derived from
anything: whether a contact is public (`contacts.owner_user_id IS NULL`) is a
property of the data, and whether an account may look at it is a property of
the billing relationship. Folding one into the other means reworking the schema
the first time pricing changes.

`users.is_admin` is the operator role. Nothing in the application ever writes
it - it is set by hand, in SQL, exactly like this:

    UPDATE users SET is_admin = true WHERE email = '...';

That is not an oversight to be fixed later. It is what guarantees no request
can escalate to admin, because no handler accepts the column at all.

`payment_requests` is the queue. Payment happens outside this system entirely -
a UPI transfer the user makes from their own bank app - so a row here is a
claim plus a screenshot, waiting for a human to believe it.

**No RLS on `payment_requests`**, which makes it the exception. The uniform
policy is `user_id = current_setting('app.user_id')`, and the operator has to
read claims across every user; under that predicate an unbound session sees
zero rows rather than all of them, so no session could serve that listing.
Access is enforced in the router, and the cost is written down in the model's
docstring: the user-facing read has to filter by `user_id` itself, because for
this one table the database will not.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default so existing rows get false rather than NULL; the model
    # carries the same default so a fresh insert does not depend on the DDL.
    op.add_column(
        "users",
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "payment_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The object key in R2, never a URL - a URL here would either expire
        # and rot, or not expire and leave a payment screenshot permanently
        # fetchable by anyone who learned the link.
        sa.Column("screenshot_key", sa.Text(), nullable=False),
        sa.Column("upi_reference", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True),
            # SET NULL rather than CASCADE: deleting an operator's account must
            # not delete the record of the claims they approved.
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("notify_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_requests_user_id", "payment_requests", ["user_id"])
    # The panel's default view is "what is waiting for me", so status is the
    # column it filters on every time.
    op.create_index("ix_payment_requests_status", "payment_requests", ["status"])

    # The application role is created in 0002 and granted DML on tables that
    # existed then; ALTER DEFAULT PRIVILEGES covers tables created since. That
    # only holds for tables created by the same role that ran 0002, which is
    # the case here, so no explicit GRANT is needed.


def downgrade() -> None:
    op.drop_index("ix_payment_requests_status", table_name="payment_requests")
    op.drop_index("ix_payment_requests_user_id", table_name="payment_requests")
    op.drop_table("payment_requests")
    op.drop_column("users", "is_admin")
    op.drop_column("users", "is_paid")
