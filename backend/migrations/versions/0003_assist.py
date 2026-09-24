"""assist sessions, participants and invites

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.create_table(
        "assist_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("service_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("end_reason", sa.Text()),
        sa.Column("last_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", pg.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('waiting', 'active', 'ended')", name="ck_assist_sessions_status"),
        sa.CheckConstraint(
            "end_reason is null or "
            "end_reason in ('owner_ended', 'service_submitted', 'expired', 'cancelled')",
            name="ck_assist_sessions_end_reason",
        ),
    )
    op.create_index(
        "ux_assist_sessions_live",
        "assist_sessions",
        ["service_session_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'ended'"),
    )
    op.create_index("ix_assist_sessions_owner", "assist_sessions", ["owner_id", sa.text("created_at desc")])
    op.create_index("ix_assist_sessions_activity", "assist_sessions", ["status", "last_activity_at"])

    op.create_table(
        "assist_invites",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assist_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("target_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("used_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind in ('link', 'trusted_call')", name="ck_assist_invites_kind"),
    )
    op.create_index("ix_assist_invites_session", "assist_invites", ["assist_session_id"])

    op.create_table(
        "assist_participants",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assist_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("joined_via", sa.Text(), nullable=False),
        sa.Column(
            "invite_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_invites.id", ondelete="SET NULL"),
        ),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("badge_label", sa.Text()),
        sa.Column("badge_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind in ('human', 'ai')", name="ck_assist_participants_kind"),
        sa.CheckConstraint(
            "role in ('owner', 'trusted_helper', 'invited_helper', 'government_operator', 'ai_agent')",
            name="ck_assist_participants_role",
        ),
        sa.CheckConstraint(
            "status in ('pending', 'active', 'left', 'rejected', 'removed')",
            name="ck_assist_participants_status",
        ),
        sa.CheckConstraint(
            "joined_via in ('owner', 'trusted_call', 'invite_link', 'operator_queue', 'ai')",
            name="ck_assist_participants_joined_via",
        ),
    )
    op.create_index(
        "ux_assist_participants_user",
        "assist_participants",
        ["assist_session_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id is not null"),
    )
    op.create_index("ix_assist_participants_user_status", "assist_participants", ["user_id", "status"])


def downgrade() -> None:
    op.drop_table("assist_participants")
    op.drop_table("assist_invites")
    op.drop_table("assist_sessions")
