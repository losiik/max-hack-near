"""application number sequence

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.execute("create sequence application_number_seq")
    op.execute(
        "select setval('application_number_seq', "
        "coalesce(max(substring(application_number from '[0-9]+$')::bigint), 0) + 1, false) "
        "from service_sessions"
    )


def downgrade() -> None:
    op.execute("drop sequence application_number_seq")
