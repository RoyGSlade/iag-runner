"""add rulings table

Revision ID: 0012_add_rulings
Revises: 0011_add_memory_cards
Create Date: 2026-01-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_add_rulings"
down_revision = "0011_add_memory_cards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rulings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("ruling", sa.Text, nullable=False),
        sa.Column("affected_systems_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("rulings")
