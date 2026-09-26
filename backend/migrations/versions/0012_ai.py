"""what the digital employee said and did

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0012"
down_revision = "0011"


def upgrade() -> None:
    op.create_table(
        "ai_agent_turns",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assist_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "participant_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=False),
        sa.Column("tools", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("guard_result", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "trigger in ('greeting', 'question', 'validation_failed', 'confusion', 'step_changed')",
            name="ck_ai_agent_turns_trigger",
        ),
        sa.CheckConstraint("guard_result in ('passed', 'rejected')", name="ck_ai_agent_turns_guard_result"),
    )
    op.create_index("ix_ai_agent_turns_session", "ai_agent_turns", ["assist_session_id", "created_at"])


def downgrade() -> None:
    op.drop_table("ai_agent_turns")
