"""Let the worker find work it is not yet bound to.

Revision ID: 0012
Revises: 0011

Every background job starts the same way: sweep for rows across all users,
then bind to one user at a time and act. The sweep half was doing that on an
unbound session, and an unbound session sees nothing - the isolation policy
compares `user_id` against `nullif(current_setting('app.user_id', true), '')`,
which is NULL, and NULL compares as false. So `tick` read zero due rows every
two minutes and reported "sent 0, skipped 0" while queued sends sat there past
their time. The same silence covered `renew_watches` (Gmail push expires after
about a week and then stops delivering), `reconcile`, `notify_due` and
`sync_calendars`.

The fix is not a BYPASSRLS role for the worker. That exempts every query on the
connection, including the per-user work after the sweep, and the reason the
worker binds per row is so the same policy that protects a request protects a
job. Instead, following `find_user_id_by_google_sub` from 0001: a small number
of SECURITY DEFINER functions, each answering exactly one question, each
returning ids and never rows. Knowing that a schedule row is due tells the
caller nothing about who it is for or what it says; reading it still requires
being bound to its owner.

EXECUTE is revoked from PUBLIC and granted to the application role only -
otherwise `CREATE FUNCTION` leaves them callable by every role on the server.

One dependency worth naming, because it is invisible: SECURITY DEFINER runs as
the function's owner, and FORCE ROW LEVEL SECURITY subjects even the table
owner to the policies. What actually lifts them here is that migrations run as
a superuser, and superusers bypass RLS regardless of FORCE. That is the same
footing `find_user_id_by_google_sub` has stood on since 0001 - so if sign-in
works on a deployment, these work too. Run this migration as the same role
that ran the others; run it as `outreach_app` and it will create functions
that return nothing.
"""
from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

APP_ROLE = "outreach_app"

_FUNCTIONS = (
    # Ids only, oldest first, so the worker's ordering and cap survive.
    """
    CREATE FUNCTION due_schedule_rows(p_limit integer)
    RETURNS TABLE (id uuid, user_id uuid)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $$
        SELECT s.id, s.user_id
        FROM public.schedule s
        WHERE s.state = 'pending' AND s.due_at <= now()
        ORDER BY s.due_at
        LIMIT p_limit
    $$
    """,
    # Connected accounts. The per-user jobs re-read the user once bound, so a
    # row that changes between sweep and bind is handled there, not here.
    """
    CREATE FUNCTION connected_user_ids()
    RETURNS TABLE (user_id uuid)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $$
        SELECT u.id FROM public.users u WHERE u.disconnected_at IS NULL
    $$
    """,
    # A count per user, not the rows: notify_due only ever needed "how many".
    """
    CREATE FUNCTION pending_counts_by_user(p_horizon timestamptz)
    RETURNS TABLE (user_id uuid, pending bigint)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $$
        SELECT s.user_id, count(*)
        FROM public.schedule s
        WHERE s.state = 'pending' AND s.due_at <= p_horizon
        GROUP BY s.user_id
    $$
    """,
)

_SIGNATURES = (
    "due_schedule_rows(integer)",
    "connected_user_ids()",
    "pending_counts_by_user(timestamptz)",
)


def upgrade() -> None:
    for statement in _FUNCTIONS:
        op.execute(statement)

    for signature in _SIGNATURES:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in _SIGNATURES:
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
