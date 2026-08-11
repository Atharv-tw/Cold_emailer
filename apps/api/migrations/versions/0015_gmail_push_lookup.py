"""Let Gmail push identify the account before binding RLS.

Revision ID: 0015
Revises: 0014

The Pub/Sub endpoint receives a mailbox email from Gmail, not an authenticated
browser session with our user UUID. It therefore has to translate email to UUID
before it can set ``app.user_id``. Querying ``users`` directly at that point
cannot work: the session is deliberately unbound and the self-only RLS policy
correctly hides every row, so every valid notification was silently ignored.

As with sign-in and the worker sweeps, the fix is a narrow SECURITY DEFINER
function rather than a role that bypasses RLS. It answers one question and
returns only an id; the endpoint binds that id before reading any user-owned
row. Disconnected accounts are excluded because their notifications should be
ignored.

EXECUTE is revoked from PUBLIC and granted only to the application role.
"""
from __future__ import annotations

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

APP_ROLE = "outreach_app"
SIGNATURE = "find_connected_user_id_by_email(text)"


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION find_connected_user_id_by_email(p_email text)
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT u.id
            FROM public.users u
            WHERE u.email = lower(p_email)
              AND u.disconnected_at IS NULL
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {SIGNATURE}")
