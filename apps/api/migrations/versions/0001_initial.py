"""Initial schema, with row-level security on every user-owned table.

Revision ID: 0001
Revises:
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Kept in step with app.models.USER_SCOPED_TABLES.
USER_SCOPED_TABLES = [
    "google_tokens", "gmail_watch", "profiles", "profile_projects",
    "profile_experience", "resumes", "targets", "messages", "schedule",
    "events", "suppression", "push_subs",
]

# Hard ceiling on touches per target. The worker enforces this too, but a
# constraint here means a bug in the worker cannot quietly write a fourth
# touch: the transaction fails instead of a stranger getting a fourth email.
MAX_TOUCHES = 3


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _user_fk(nullable: bool = False, index: bool = True) -> sa.Column:
    return sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=nullable,
        index=index,
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("avatar", sa.Text(), nullable=False, server_default=""),
        sa.Column("disconnected_at", sa.DateTime(timezone=True)),
        sa.Column("disconnected_reason", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
    )

    op.create_table(
        "google_tokens",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )

    op.create_table(
        "gmail_watch",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("history_id", sa.BigInteger()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )

    op.create_table(
        "profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("headline", sa.Text(), nullable=False, server_default=""),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("links", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("education", sa.Text(), nullable=False, server_default=""),
        sa.Column("availability", sa.Text(), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("sending_window", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("daily_cap", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("first_send_date", sa.Date()),
        *_timestamps(),
        # The cap is server-side and not raisable from the UI. This keeps a
        # stray API call from turning the product into a marketing blaster.
        sa.CheckConstraint("daily_cap > 0 AND daily_cap <= 50", name="ck_profiles_daily_cap"),
    )

    op.create_table(
        "profile_projects",
        _uuid_pk(),
        _user_fk(),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("tech", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("highlights", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("categories", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("best_for", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )

    op.create_table(
        "profile_experience",
        _uuid_pk(),
        _user_fk(),
        sa.Column("company", sa.String(255), nullable=False, server_default=""),
        sa.Column("role", sa.String(255), nullable=False, server_default=""),
        sa.Column("started", sa.String(32), nullable=False, server_default=""),
        sa.Column("ended", sa.String(32), nullable=False, server_default=""),
        sa.Column("bullets", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )

    op.create_table(
        "resumes",
        _uuid_pk(),
        _user_fk(),
        sa.Column("filename", sa.String(512), nullable=False, server_default=""),
        sa.Column("storage_key", sa.String(512), nullable=False, server_default=""),
        sa.Column("parsed", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("parsed_at", sa.DateTime(timezone=True)),
        sa.Column("keep_original", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("original_deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )

    op.create_table(
        "targets",
        _uuid_pk(),
        _user_fk(),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("company", sa.String(255), nullable=False, server_default=""),
        sa.Column("role", sa.String(255), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("company_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(64), nullable=False, server_default=""),
        sa.Column("hook", sa.Text(), nullable=False, server_default=""),
        sa.Column("intent", sa.String(64), nullable=False, server_default=""),
        sa.Column("links", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("verification", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
        sa.Column("status_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("gmail_thread_id", sa.String(64), index=True),
        sa.Column("last_message_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("thread_refs", sa.Text(), nullable=False, server_default=""),
        sa.Column("thread_subject", sa.Text(), nullable=False, server_default=""),
        sa.Column("touches_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_touch_at", sa.DateTime(timezone=True)),
        sa.Column("thread_checked_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "email", name="uq_targets_user_email"),
        sa.CheckConstraint(
            f"touches_sent >= 0 AND touches_sent <= {MAX_TOUCHES}",
            name="ck_targets_touch_ceiling",
        ),
    )

    op.create_table(
        "messages",
        _uuid_pk(),
        _user_fk(),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("targets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("gmail_message_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("rfc822_message_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
    )

    op.create_table(
        "schedule",
        _uuid_pk(),
        _user_fk(),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("targets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="pending", index=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("google_event_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("event_synced_due_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("target_id", "step", name="uq_schedule_target_step"),
        sa.CheckConstraint(f"step >= 1 AND step <= {MAX_TOUCHES}", name="ck_schedule_step_ceiling"),
    )

    op.create_table(
        "events",
        _uuid_pk(),
        _user_fk(),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("targets.id", ondelete="CASCADE"),
            index=True,
        ),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
    )

    op.create_table(
        "suppression",
        _uuid_pk(),
        _user_fk(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "email", name="uq_suppression_user_email"),
    )

    op.create_table(
        "recipient_guard",
        sa.Column("email_key", sa.String(64), primary_key=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contact_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "push_subs",
        _uuid_pk(),
        _user_fk(),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("keys", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "endpoint", name="uq_push_user_endpoint"),
    )

    # The worker's hot query: everything due, oldest first.
    op.create_index(
        "ix_schedule_due_pending",
        "schedule",
        ["due_at"],
        postgresql_where=sa.text("state = 'pending'"),
    )

    _enable_rls()


def _enable_rls() -> None:
    """Second line of defence behind the per-query user_id filter.

    FORCE is the important word. Without it the table owner - which is the
    role the application connects as in most deployments - bypasses its own
    policies, and the protection silently does nothing.

    `nullif(..., '')` matters too: an unbound session leaves the setting as an
    empty string, and casting that to uuid raises rather than matching. NULL
    compares as false, so an unbound session sees no rows instead of erroring
    on every query.
    """
    predicate = "user_id = nullif(current_setting('app.user_id', true), '')::uuid"

    for table in USER_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_isolation ON {table} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY users_isolation ON users "
        "USING (id = nullif(current_setting('app.user_id', true), '')::uuid) "
        "WITH CHECK (id = nullif(current_setting('app.user_id', true), '')::uuid)"
    )

    # Sign-in is the one flow that has to find a user *before* there is a user
    # to bind the session to, which RLS would otherwise block. Rather than
    # running sign-in as a BYPASSRLS role - which would exempt every query on
    # that connection, not just this lookup - expose exactly one SECURITY
    # DEFINER function that answers exactly one question.
    #
    # It returns an id, never a row, so it cannot be used to read anyone's
    # profile; and it takes a google_sub, which the caller only knows because
    # Google just signed a token asserting it.
    op.execute(
        """
        CREATE FUNCTION find_user_id_by_google_sub(p_sub text)
        RETURNS uuid
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$ SELECT id FROM public.users WHERE google_sub = p_sub $$
        """
    )

    # recipient_guard is deliberately not user-scoped: seeing across users is
    # its entire purpose, and it holds keyed hashes rather than addresses.


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS find_user_id_by_google_sub(text)")
    for table in [*USER_SCOPED_TABLES, "users"]:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")

    op.drop_index("ix_schedule_due_pending", table_name="schedule")
    for table in (
        "push_subs", "recipient_guard", "suppression", "events", "schedule",
        "messages", "targets", "resumes", "profile_experience",
        "profile_projects", "profiles", "gmail_watch", "google_tokens", "users",
    ):
        op.drop_table(table)
