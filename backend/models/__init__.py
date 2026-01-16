from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attributes_json: Mapped[dict | None] = mapped_column(JSONB)


class Profession(Base):
    __tablename__ = "professions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attributes_json: Mapped[dict | None] = mapped_column(JSONB)
    gear_pack_json: Mapped[dict | None] = mapped_column(JSONB)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    definition_json: Mapped[dict | None] = mapped_column(JSONB)


class Training(Base):
    __tablename__ = "trainings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    skill_levels_json: Mapped[dict | None] = mapped_column(JSONB)


class Leveling(Base):
    __tablename__ = "leveling"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attributes_json: Mapped[dict | None] = mapped_column(JSONB)
    skill_levels_json: Mapped[dict | None] = mapped_column(JSONB)


class SuperPower(Base):
    __tablename__ = "super_powers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    definition_json: Mapped[dict | None] = mapped_column(JSONB)


class Status(Base):
    __tablename__ = "statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    progression_json: Mapped[dict | None] = mapped_column(JSONB)


class Era(Base):
    __tablename__ = "eras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[dict | None] = mapped_column(JSONB)
    patch_json: Mapped[dict | None] = mapped_column(JSONB)


class ArmorBase(Base):
    __tablename__ = "armor_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    armor_rating: Mapped[int | None] = mapped_column(Integer)
    stats_json: Mapped[dict | None] = mapped_column(JSONB)


class ArmorVariation(Base):
    __tablename__ = "armor_variations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_id: Mapped[int] = mapped_column(ForeignKey("armor_bases.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    modifier_json: Mapped[dict | None] = mapped_column(JSONB)


class ShieldBase(Base):
    __tablename__ = "shield_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    block_value: Mapped[int | None] = mapped_column(Integer)
    stats_json: Mapped[dict | None] = mapped_column(JSONB)


class WeaponBase(Base):
    __tablename__ = "weapon_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    damage: Mapped[str | None] = mapped_column(String(80))
    damage_type: Mapped[str | None] = mapped_column(String(80))
    stats_json: Mapped[dict | None] = mapped_column(JSONB)


class WeaponVariation(Base):
    __tablename__ = "weapon_variations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_id: Mapped[int] = mapped_column(ForeignKey("weapon_bases.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    modifier_json: Mapped[dict | None] = mapped_column(JSONB)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    attachment_type: Mapped[str | None] = mapped_column(String(80))
    modifier_json: Mapped[dict | None] = mapped_column(JSONB)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    rng_seed: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    race_id: Mapped[int | None] = mapped_column(ForeignKey("races.id"))
    profession_id: Mapped[int | None] = mapped_column(ForeignKey("professions.id"))
    training_id: Mapped[int | None] = mapped_column(ForeignKey("trainings.id"))
    level: Mapped[int | None] = mapped_column(Integer)
    attributes_json: Mapped[dict | None] = mapped_column(JSONB)
    skill_levels_json: Mapped[dict | None] = mapped_column(JSONB)
    gear_pack_json: Mapped[dict | None] = mapped_column(JSONB)
    statuses_json: Mapped[dict | None] = mapped_column(JSONB)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    character_id: Mapped[int | None] = mapped_column(ForeignKey("characters.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    requirements_json: Mapped[dict | None] = mapped_column(JSONB)
    constraints_json: Mapped[dict | None] = mapped_column(JSONB)
    work_units_total: Mapped[int] = mapped_column(Integer, nullable=False)
    work_units_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class Monster(Base):
    __tablename__ = "monsters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    stats_json: Mapped[dict | None] = mapped_column(JSONB)
    abilities_json: Mapped[dict | None] = mapped_column(JSONB)
    weakness_json: Mapped[dict | None] = mapped_column(JSONB)
    tags_json: Mapped[dict | None] = mapped_column(JSONB)
    era: Mapped[str | None] = mapped_column(String(80))


class NPC(Base):
    __tablename__ = "npcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    faction_id: Mapped[int | None] = mapped_column(Integer)
    personality_json: Mapped[dict | None] = mapped_column(JSONB)
    goals_json: Mapped[dict | None] = mapped_column(JSONB)
    fears_json: Mapped[dict | None] = mapped_column(JSONB)
    secrets_json: Mapped[dict | None] = mapped_column(JSONB)
    relationships_json: Mapped[dict | None] = mapped_column(JSONB)
    stats_json: Mapped[dict | None] = mapped_column(JSONB)
    voice_json: Mapped[dict | None] = mapped_column(JSONB)


class EntityLink(Base):
    __tablename__ = "entity_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_type: Mapped[str] = mapped_column(String(80), nullable=False)
    to_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relation: Mapped[str] = mapped_column(String(80), nullable=False)
    secrecy_level: Mapped[str] = mapped_column(String(20), nullable=False)


class Secret(Base):
    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    secret_text: Mapped[str] = mapped_column(Text, nullable=False)
    linked_entities_json: Mapped[dict | None] = mapped_column(JSONB)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    era: Mapped[str | None] = mapped_column(String(80))
    tags_json: Mapped[dict | None] = mapped_column(JSONB)
    card_json: Mapped[dict | None] = mapped_column(JSONB)


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    description_json: Mapped[dict | None] = mapped_column(JSONB)
    objects_json: Mapped[dict | None] = mapped_column(JSONB)
    npcs_present_json: Mapped[dict | None] = mapped_column(JSONB)
    exits_json: Mapped[dict | None] = mapped_column(JSONB)
    hazards_json: Mapped[dict | None] = mapped_column(JSONB)


class Clock(Base):
    __tablename__ = "clocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    steps_total: Mapped[int] = mapped_column(Integer, nullable=False)
    steps_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadline_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visibility: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_tags_json: Mapped[dict | None] = mapped_column(JSONB)


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    urgency: Mapped[str] = mapped_column(String(10), nullable=False)
    visibility: Mapped[str] = mapped_column(String(10), nullable=False)
    related_entities_json: Mapped[dict | None] = mapped_column(JSONB)
    text: Mapped[str] = mapped_column(String(280), nullable=False)


class MemoryCard(Base):
    __tablename__ = "memory_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String(160))
    summary_text: Mapped[str | None] = mapped_column(Text)
    facts_json: Mapped[list | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Ruling(Base):
    __tablename__ = "rulings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    ruling: Mapped[str] = mapped_column(Text, nullable=False)
    affected_systems_json: Mapped[list | None] = mapped_column(JSONB)


class SystemDraft(Base):
    __tablename__ = "system_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    inputs_json: Mapped[list | None] = mapped_column(JSONB)
    process_json: Mapped[list | None] = mapped_column(JSONB)
    outputs_json: Mapped[list | None] = mapped_column(JSONB)
    costs_json: Mapped[list | None] = mapped_column(JSONB)
    risks_json: Mapped[list | None] = mapped_column(JSONB)
    checks_json: Mapped[list | None] = mapped_column(JSONB)


class Discovery(Base):
    __tablename__ = "discoveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    gradient: Mapped[str] = mapped_column(String(20), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[list | None] = mapped_column(JSONB)
    context_json: Mapped[dict | None] = mapped_column(JSONB)


class PlayerProfile(Base):
    __tablename__ = "player_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    tone_prefs_json: Mapped[dict | None] = mapped_column(JSONB)
    themes_json: Mapped[dict | None] = mapped_column(JSONB)
    pacing_json: Mapped[dict | None] = mapped_column(JSONB)
    challenge_json: Mapped[dict | None] = mapped_column(JSONB)
    boundaries_json: Mapped[dict | None] = mapped_column(JSONB)
    interests_json: Mapped[dict | None] = mapped_column(JSONB)
