"""add npcs table

Revision ID: 0005_add_npcs
Revises: 0004_add_monsters
Create Date: 2026-01-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_add_npcs"
down_revision = "0004_add_monsters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "npcs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("faction_id", sa.Integer),
        sa.Column("personality_json", postgresql.JSONB),
        sa.Column("goals_json", postgresql.JSONB),
        sa.Column("fears_json", postgresql.JSONB),
        sa.Column("secrets_json", postgresql.JSONB),
        sa.Column("relationships_json", postgresql.JSONB),
        sa.Column("stats_json", postgresql.JSONB),
        sa.Column("voice_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("npcs")
