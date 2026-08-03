"""Give the application a non-superuser role, so RLS actually applies.

Revision ID: 0002
Revises: 0001

Row-level security has one exemption that is easy to miss: superusers bypass
it completely, and FORCE ROW LEVEL SECURITY does not change that. The default
Postgres container makes POSTGRES_USER a superuser, so an application
connecting as it sees every row of every user's data no matter how carefully
the policies are written.

That is not a theoretical gap. Bound to one user, a superuser connection could
read another user's targets and insert rows owned by them.

So there are two roles from here on:

    outreach       owns the schema, runs migrations, superuser
    outreach_app   what the application and worker connect as, no bypass

The application role gets DML on the tables and nothing else - no DDL, no
ownership, and therefore no way to drop a policy it does not like.
"""
from __future__ import annotations

import os

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP_ROLE = "outreach_app"

# Local development default. Anywhere real, set APP_DB_PASSWORD.
DEFAULT_PASSWORD = "outreach_app"


def upgrade() -> None:
    password = os.environ.get("APP_DB_PASSWORD", DEFAULT_PASSWORD)

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{password}';
            ELSE
                ALTER ROLE {APP_ROLE} LOGIN PASSWORD '{password}';
            END IF;
        END
        $$;
        """
    )

    # Explicitly *not* granted: CREATE on the schema, ownership of anything,
    # and BYPASSRLS. The application can read and write rows the policies
    # allow, and cannot change the policies.
    op.execute(f"GRANT CONNECT ON DATABASE {_database()} TO {APP_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {APP_ROLE}")

    # Tables created by later migrations, so this does not need repeating.
    owner = op.get_bind().exec_driver_sql("SELECT current_user").scalar()
    for statement in (
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}",
        f"GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}",
        f"GRANT EXECUTE ON FUNCTIONS TO {APP_ROLE}",
    ):
        op.execute(f'ALTER DEFAULT PRIVILEGES FOR ROLE "{owner}" IN SCHEMA public {statement}')

    # alembic_version is the migration runner's own bookkeeping. The
    # application has no business writing it.
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM {APP_ROLE}")


def _database() -> str:
    return op.get_bind().exec_driver_sql("SELECT current_database()").scalar()


def downgrade() -> None:
    op.execute(f"REASSIGN OWNED BY {APP_ROLE} TO CURRENT_USER")
    op.execute(f"DROP OWNED BY {APP_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")
