"""add monsters table

Revision ID: 0004_add_monsters
Revises: 0003_add_projects
Create Date: 2026-01-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_add_monsters"
down_revision = "0003_add_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monsters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("stats_json", postgresql.JSONB),
        sa.Column("abilities_json", postgresql.JSONB),
        sa.Column("weakness_json", postgresql.JSONB),
        sa.Column("tags_json", postgresql.JSONB),
        sa.Column("era", sa.String(length=80)),
    )


def downgrade() -> None:
    op.drop_table("monsters")
