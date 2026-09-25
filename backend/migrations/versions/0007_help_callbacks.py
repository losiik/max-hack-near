"""busy helpers and their promise to come back

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    op.add_column("assist_invites", sa.Column("declined_at", sa.DateTime(timezone=True)))
    op.add_column(
        "assist_invites",
        sa.Column("declined_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )

    op.create_table(
        "help_callbacks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "helper_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("service_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status in ('busy', 'ready', 'used', 'dismissed')",
            name="ck_help_callbacks_status",
        ),
    )
    op.create_index(
        "ux_help_callbacks_open",
        "help_callbacks",
        ["owner_id", "helper_id", "service_session_id"],
        unique=True,
        postgresql_where=sa.text("status in ('busy', 'ready')"),
    )
    op.create_index("ix_help_callbacks_owner", "help_callbacks", ["owner_id", "status"])
    op.create_index("ix_help_callbacks_helper", "help_callbacks", ["helper_id", "status"])


def downgrade() -> None:
    op.drop_table("help_callbacks")
    op.drop_column("assist_invites", "declined_by")
    op.drop_column("assist_invites", "declined_at")
