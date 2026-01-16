"""add player profile table

Revision ID: 0015_add_player_profile
Revises: 0014_add_discoveries
Create Date: 2026-01-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_add_player_profile"
down_revision = "0014_add_discoveries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_profile",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("tone_prefs_json", postgresql.JSONB),
        sa.Column("themes_json", postgresql.JSONB),
        sa.Column("pacing_json", postgresql.JSONB),
        sa.Column("challenge_json", postgresql.JSONB),
        sa.Column("boundaries_json", postgresql.JSONB),
        sa.Column("interests_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("player_profile")
