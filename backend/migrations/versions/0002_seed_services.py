"""seed demo services

Revision ID: 0002
Revises: 0001
"""

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FILES = ["housing_compensation_v1.json"]


def upgrade() -> None:
    services = sa.table(
        "services",
        sa.column("code", sa.Text),
        sa.column("version", sa.Integer),
        sa.column("title", sa.Text),
        sa.column("short_description", sa.Text),
        sa.column("estimated_minutes", sa.Integer),
        sa.column("disclaimer", sa.Text),
        sa.column("is_demo", sa.Boolean),
        sa.column("is_published", sa.Boolean),
        sa.column("definition", sa.JSON),
    )

    rows = []
    for name in FILES:
        definition = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
        rows.append(
            {
                "code": definition["code"],
                "version": definition["version"],
                "title": definition["title"],
                "short_description": definition["short_description"],
                "estimated_minutes": definition["estimated_minutes"],
                "disclaimer": definition.get("disclaimer"),
                "is_demo": True,
                "is_published": True,
                "definition": definition,
            }
        )

    op.bulk_insert(services, rows)


def downgrade() -> None:
    codes = [json.loads((DATA_DIR / name).read_text(encoding="utf-8"))["code"] for name in FILES]
    op.execute(sa.text("delete from services where code = any(:codes)").bindparams(codes=codes))
