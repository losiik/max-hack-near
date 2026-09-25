"""meetings outlive the application they were about

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"

FOREIGN_KEY = "assist_sessions_service_session_id_fkey"
OWNER_KEY = "assist_sessions_owner_id_fkey"


def owner_key(ondelete: str | None) -> None:
    op.drop_constraint(OWNER_KEY, "assist_sessions", type_="foreignkey")
    op.create_foreign_key(OWNER_KEY, "assist_sessions", "users", ["owner_id"], ["id"], ondelete=ondelete)


def upgrade() -> None:
    op.add_column("assist_sessions", sa.Column("service_code", sa.Text()))
    op.add_column("assist_sessions", sa.Column("service_version", sa.Integer()))
    op.execute(
        """
        update assist_sessions a
        set service_code = s.service_code, service_version = s.service_version
        from service_sessions s
        where s.id = a.service_session_id
        """
    )
    op.alter_column("assist_sessions", "service_code", nullable=False)
    op.alter_column("assist_sessions", "service_version", nullable=False)

    op.drop_constraint(FOREIGN_KEY, "assist_sessions", type_="foreignkey")
    op.alter_column("assist_sessions", "service_session_id", nullable=True)
    op.create_foreign_key(
        FOREIGN_KEY,
        "assist_sessions",
        "service_sessions",
        ["service_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    owner_key("CASCADE")
    op.create_index(
        "ix_assist_sessions_owner_service",
        "assist_sessions",
        ["owner_id", "service_code", sa.text("ended_at desc")],
    )


def downgrade() -> None:
    op.drop_index("ix_assist_sessions_owner_service", "assist_sessions")
    owner_key(None)
    op.execute("delete from assist_sessions where service_session_id is null")
    op.drop_constraint(FOREIGN_KEY, "assist_sessions", type_="foreignkey")
    op.alter_column("assist_sessions", "service_session_id", nullable=False)
    op.create_foreign_key(
        FOREIGN_KEY,
        "assist_sessions",
        "service_sessions",
        ["service_session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("assist_sessions", "service_version")
    op.drop_column("assist_sessions", "service_code")
