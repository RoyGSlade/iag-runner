"""add projects table

Revision ID: 0003_add_projects
Revises: 0002_add_character_statuses
Create Date: 2026-01-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_add_projects"
down_revision = "0002_add_character_statuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column("character_id", sa.Integer, sa.ForeignKey("characters.id")),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("requirements_json", postgresql.JSONB),
        sa.Column("constraints_json", postgresql.JSONB),
        sa.Column("work_units_total", sa.Integer, nullable=False),
        sa.Column("work_units_done", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )


def downgrade() -> None:
    op.drop_table("projects")
