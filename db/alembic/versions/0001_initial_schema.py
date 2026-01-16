"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-01-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "races",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("attributes_json", postgresql.JSONB),
    )

    op.create_table(
        "professions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("attributes_json", postgresql.JSONB),
        sa.Column("gear_pack_json", postgresql.JSONB),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("definition_json", postgresql.JSONB),
    )

    op.create_table(
        "trainings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("skill_levels_json", postgresql.JSONB),
    )

    op.create_table(
        "leveling",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("attributes_json", postgresql.JSONB),
        sa.Column("skill_levels_json", postgresql.JSONB),
    )

    op.create_table(
        "super_powers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("definition_json", postgresql.JSONB),
    )

    op.create_table(
        "statuses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("progression_json", postgresql.JSONB),
    )

    op.create_table(
        "eras",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("profile_json", postgresql.JSONB),
        sa.Column("patch_json", postgresql.JSONB),
    )

    op.create_table(
        "armor_bases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("armor_rating", sa.Integer),
        sa.Column("stats_json", postgresql.JSONB),
    )

    op.create_table(
        "shield_bases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("block_value", sa.Integer),
        sa.Column("stats_json", postgresql.JSONB),
    )

    op.create_table(
        "weapon_bases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("damage", sa.String(length=80)),
        sa.Column("damage_type", sa.String(length=80)),
        sa.Column("stats_json", postgresql.JSONB),
    )

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("attachment_type", sa.String(length=80)),
        sa.Column("modifier_json", postgresql.JSONB),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rng_seed", sa.Integer),
        sa.Column("metadata_json", postgresql.JSONB),
    )

    op.create_table(
        "armor_variations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("base_id", sa.Integer, sa.ForeignKey("armor_bases.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("modifier_json", postgresql.JSONB),
    )

    op.create_table(
        "weapon_variations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("base_id", sa.Integer, sa.ForeignKey("weapon_bases.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("modifier_json", postgresql.JSONB),
    )

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id")),
        sa.Column("profession_id", sa.Integer, sa.ForeignKey("professions.id")),
        sa.Column("training_id", sa.Integer, sa.ForeignKey("trainings.id")),
        sa.Column("level", sa.Integer),
        sa.Column("attributes_json", postgresql.JSONB),
        sa.Column("skill_levels_json", postgresql.JSONB),
        sa.Column("gear_pack_json", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("characters")
    op.drop_table("weapon_variations")
    op.drop_table("armor_variations")
    op.drop_table("sessions")
    op.drop_table("attachments")
    op.drop_table("weapon_bases")
    op.drop_table("shield_bases")
    op.drop_table("armor_bases")
    op.drop_table("eras")
    op.drop_table("statuses")
    op.drop_table("super_powers")
    op.drop_table("leveling")
    op.drop_table("trainings")
    op.drop_table("skills")
    op.drop_table("professions")
    op.drop_table("races")
