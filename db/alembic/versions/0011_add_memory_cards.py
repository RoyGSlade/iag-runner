"""add memory cards table

Revision ID: 0011_add_memory_cards
Revises: 0010_update_threads
Create Date: 2026-01-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_add_memory_cards"
down_revision = "0010_update_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_cards",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer),
        sa.Column("name", sa.String(length=160)),
        sa.Column("summary_text", sa.Text),
        sa.Column("facts_json", postgresql.JSONB),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("memory_cards")
