"""mfc staff and their queue of requests

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0010"
down_revision = "0009"


def upgrade() -> None:
    op.create_table(
        "staff_profiles",
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("organization", sa.Text(), nullable=False),
        sa.Column("position", sa.Text()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("role in ('mfc_operator')", name="ck_staff_profiles_role"),
    )

    op.create_table(
        "operator_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assist_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("context", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("claimed_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("source in ('owner', 'ai_escalation')", name="ck_operator_requests_source"),
        sa.CheckConstraint(
            "status in ('queued', 'claimed', 'completed', 'cancelled')",
            name="ck_operator_requests_status",
        ),
        sa.CheckConstraint(
            "topic in ('dont_understand', 'form_error', 'other')",
            name="ck_operator_requests_topic",
        ),
    )
    op.create_index("ix_operator_requests_queue", "operator_requests", ["status", "created_at"])
    op.create_index(
        "ux_operator_requests_open",
        "operator_requests",
        ["assist_session_id"],
        unique=True,
        postgresql_where=sa.text("status in ('queued', 'claimed')"),
    )


def downgrade() -> None:
    op.drop_table("operator_requests")
    op.drop_table("staff_profiles")
