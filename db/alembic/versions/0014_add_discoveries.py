"""add discoveries table

Revision ID: 0014_add_discoveries
Revises: 0013_add_system_drafts
Create Date: 2026-01-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_add_discoveries"
down_revision = "0013_add_system_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discoveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("gradient", sa.String(length=20), nullable=False),
        sa.Column("summary_text", sa.Text, nullable=False),
        sa.Column("tags_json", postgresql.JSONB),
        sa.Column("context_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("discoveries")
