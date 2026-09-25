"""audio recordings of meetings

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    op.create_table(
        "recordings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assist_session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assist_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("egress_id", sa.Text()),
        sa.Column("file_path", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.CheckConstraint(
            "status in ('recording', 'ready', 'failed', 'deleted')",
            name="ck_recordings_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("recordings")
