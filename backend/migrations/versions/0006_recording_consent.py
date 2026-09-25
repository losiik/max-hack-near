"""consent to record meetings

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    op.add_column("users", sa.Column("recording_consent_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("users", "recording_consent_at")
