"""session events journal

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.create_table(
        "session_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "assist_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_participant_id", pg.UUID(as_uuid=True)),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        "ix_session_events_timeline",
        "session_events",
        ["assist_session_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("session_events")
