"""add clocks table

Revision ID: 0008_add_clocks
Revises: 0007_add_locations_scenes
Create Date: 2026-01-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_add_clocks"
down_revision = "0007_add_locations_scenes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clocks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("steps_total", sa.Integer, nullable=False),
        sa.Column("steps_done", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deadline_time", sa.DateTime(timezone=True)),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("trigger_tags_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("clocks")
