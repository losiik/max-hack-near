"""initial schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("max_user_id", sa.BigInteger(), unique=True),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text()),
        sa.Column("username", sa.Text()),
        sa.Column("photo_url", sa.Text()),
        sa.Column("dev_key", sa.Text(), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "services",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("disclaimer", sa.Text()),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("definition", pg.JSONB(), nullable=False),
    )

    op.create_table(
        "service_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("service_code", sa.Text(), nullable=False),
        sa.Column("service_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_step_id", sa.Text(), nullable=False),
        sa.Column(
            "completed_step_ids",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("public_data", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sensitive_data_enc", sa.LargeBinary()),
        sa.Column("last_errors", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("confirmation_code_hash", sa.Text()),
        sa.Column("confirmation_expires_at", sa.DateTime(timezone=True)),
        sa.Column("confirmation_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("application_number", sa.Text(), unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status in ('draft', 'submitted', 'cancelled')",
            name="ck_service_sessions_status",
        ),
    )
    op.create_index(
        "ix_service_sessions_owner",
        "service_sessions",
        ["owner_id", "status", sa.text("updated_at desc")],
    )

    op.create_table(
        "service_session_inbox",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("service_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_inbox_session",
        "service_session_inbox",
        ["service_session_id", sa.text("created_at desc")],
    )


def downgrade() -> None:
    op.drop_table("service_session_inbox")
    op.drop_table("service_sessions")
    op.drop_table("services")
    op.drop_table("users")
