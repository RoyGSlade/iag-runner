"""add locations and scenes tables

Revision ID: 0007_add_locations_scenes
Revises: 0006_add_truth_graph
Create Date: 2026-01-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_add_locations_scenes"
down_revision = "0006_add_truth_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("era", sa.String(length=80)),
        sa.Column("tags_json", postgresql.JSONB),
        sa.Column("card_json", postgresql.JSONB),
    )
    op.create_table(
        "scenes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("location_id", sa.Integer, sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("description_json", postgresql.JSONB),
        sa.Column("objects_json", postgresql.JSONB),
        sa.Column("npcs_present_json", postgresql.JSONB),
        sa.Column("exits_json", postgresql.JSONB),
        sa.Column("hazards_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("scenes")
    op.drop_table("locations")
