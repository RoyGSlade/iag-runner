"""add system drafts table

Revision ID: 0013_add_system_drafts
Revises: 0012_add_rulings
Create Date: 2026-01-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_add_system_drafts"
down_revision = "0012_add_rulings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_drafts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("inputs_json", postgresql.JSONB),
        sa.Column("process_json", postgresql.JSONB),
        sa.Column("outputs_json", postgresql.JSONB),
        sa.Column("costs_json", postgresql.JSONB),
        sa.Column("risks_json", postgresql.JSONB),
        sa.Column("checks_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("system_drafts")
