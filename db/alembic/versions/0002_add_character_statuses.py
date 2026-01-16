"""add character statuses

Revision ID: 0002_add_character_statuses
Revises: 0001_initial_schema
Create Date: 2026-01-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_add_character_statuses"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("characters", sa.Column("statuses_json", postgresql.JSONB))


def downgrade() -> None:
    op.drop_column("characters", "statuses_json")
