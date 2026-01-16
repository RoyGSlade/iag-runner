"""add truth graph tables

Revision ID: 0006_add_truth_graph
Revises: 0005_add_npcs
Create Date: 2026-01-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_add_truth_graph"
down_revision = "0005_add_npcs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_links",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("from_type", sa.String(length=80), nullable=False),
        sa.Column("from_id", sa.Integer, nullable=False),
        sa.Column("to_type", sa.String(length=80), nullable=False),
        sa.Column("to_id", sa.Integer, nullable=False),
        sa.Column("relation", sa.String(length=80), nullable=False),
        sa.Column("secrecy_level", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "secrets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_type", sa.String(length=80), nullable=False),
        sa.Column("owner_id", sa.Integer, nullable=False),
        sa.Column("secret_text", sa.Text, nullable=False),
        sa.Column("linked_entities_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("secrets")
    op.drop_table("entity_links")
