"""update threads schema

Revision ID: 0010_update_threads
Revises: 0009_add_threads
Create Date: 2026-01-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_update_threads"
down_revision = "0009_add_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("threads", sa.Column("type", sa.String(length=40), nullable=True))
    op.add_column("threads", sa.Column("status", sa.String(length=20), nullable=True))
    op.add_column("threads", sa.Column("urgency", sa.String(length=10), nullable=True))
    op.add_column("threads", sa.Column("visibility", sa.String(length=10), nullable=True))
    op.add_column("threads", sa.Column("related_entities_json", postgresql.JSONB))
    op.add_column("threads", sa.Column("text", sa.String(length=280), nullable=True))


def downgrade() -> None:
    op.drop_column("threads", "text")
    op.drop_column("threads", "related_entities_json")
    op.drop_column("threads", "visibility")
    op.drop_column("threads", "urgency")
    op.drop_column("threads", "status")
    op.drop_column("threads", "type")
