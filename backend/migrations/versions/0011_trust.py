"""trusted helpers and pairing by qr or link

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0011"
down_revision = "0010"


def user_column(name: str, ondelete: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name, pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete=ondelete), nullable=nullable
    )


def upgrade() -> None:
    op.create_table(
        "pairings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        user_column("owner_id", "CASCADE"),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.Text(), nullable=False),
        user_column("claimed_by", "SET NULL", nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("method in ('qr', 'link')", name="ck_pairings_method"),
        sa.CheckConstraint(
            "status in ('pending', 'claimed', 'confirmed', 'rejected', 'expired', 'cancelled')",
            name="ck_pairings_status",
        ),
    )

    op.create_table(
        "trusted_helpers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        user_column("owner_id", "CASCADE"),
        user_column("helper_id", "CASCADE"),
        sa.Column("alias", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("verification_method", sa.Text(), nullable=False),
        sa.Column("pairing_id", pg.UUID(as_uuid=True), sa.ForeignKey("pairings.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("owner_id <> helper_id", name="ck_trusted_helpers_not_self"),
        sa.CheckConstraint("status in ('active', 'revoked')", name="ck_trusted_helpers_status"),
        sa.CheckConstraint(
            "verification_method in ('qr', 'invite_link')",
            name="ck_trusted_helpers_method",
        ),
    )
    op.create_index(
        "ux_trusted_helpers_pair",
        "trusted_helpers",
        ["owner_id", "helper_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_trusted_helpers_helper", "trusted_helpers", ["helper_id", "status"])


def downgrade() -> None:
    op.drop_table("trusted_helpers")
    op.drop_table("pairings")
