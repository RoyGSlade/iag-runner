from __future__ import annotations

import random
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    Character,
    Era,
    Leveling,
    PlayerProfile,
    Profession,
    Race,
    Session as SessionModel,
    Training,
)
from rules.combat import base_actions
from rules.settings import generate_location_name, normalize_setting_type

ATTRIBUTE_KEYS = ("CON", "DEX", "CHA", "WIS", "INT")
ATTRIBUTE_ALIASES = {
    "constitution": "CON",
    "con": "CON",
    "dexterity": "DEX",
    "dex": "DEX",
    "charisma": "CHA",
    "cha": "CHA",
    "wisdom": "WIS",
    "wis": "WIS",
    "intelligence": "INT",
    "int": "INT",
}


def create_session_record(
    db: Session,
    *,
    era_name: str = "Space",
    location: str | None = "Fallon Station",
    seed: int | None = None,
    metadata: dict | None = None,
    setting: dict | None = None,
    settings: dict | None = None,
) -> SessionModel:
    if seed is None:
        seed = random.randint(1, 2**31 - 1)
    metadata_json = dict(metadata or {})
    metadata_json.setdefault("era", era_name)

    settings_json: dict[str, Any] = {}
    existing_settings = metadata_json.get("settings")
    if isinstance(existing_settings, dict):
        settings_json.update(existing_settings)
    if isinstance(settings, dict):
        settings_json.update(settings)
    settings_json.setdefault("dev_mode_enabled", False)
    settings_json.setdefault("ooc_allowed", True)
    metadata_json["settings"] = settings_json

    setting_data = dict(setting or {})
    setting_type = normalize_setting_type(setting_data.get("type"), era_name=era_name)
    location_name = setting_data.get("location_name") or location
    if not location_name:
        location_name = generate_location_name(
            era_name=era_name,
            setting_type=setting_type,
            seed=seed,
        )
    setting_data["type"] = setting_type
    setting_data["location_name"] = location_name

    metadata_json.setdefault("setting", setting_data)
    metadata_json.setdefault("location", location_name)
    metadata_json.setdefault(
        "current_scene",
        _build_default_scene(
            era_name=era_name,
            location_name=location_name,
        ),
    )
    session = SessionModel(rng_seed=seed, metadata_json=metadata_json)
    db.add(session)
    db.flush()
    db.add(
        PlayerProfile(
            session_id=session.id,
            tone_prefs_json=_default_tone_prefs(metadata_json),
            themes_json=_default_themes(metadata_json),
            pacing_json=_default_pacing(metadata_json),
            challenge_json=_default_challenge(metadata_json),
            boundaries_json=_default_boundaries(metadata_json),
            interests_json=_default_interest_weights(),
        )
    )
    return session


def create_character_record(
    db: Session,
    *,
    session: SessionModel,
    race_name: str | None,
    profession_name: str | None,
    training_name: str | None,
    level: int = 1,
    armor_value: int | None = None,
) -> Character:
    race = _get_or_create_race(db, race_name) if race_name else None
    profession = _get_or_create_profession(db, profession_name) if profession_name else None
    training = _get_or_create_training(db, training_name) if training_name else None
    leveling = db.query(Leveling).filter_by(level=level).first()

    attributes, pending = _compute_attributes(race, profession, training)
    derived = _compute_derived_stats(
        attributes,
        training,
        leveling,
        armor_value=armor_value,
    )
    era_name = (session.metadata_json or {}).get("era")
    era = _get_by_name(db, Era, era_name) if era_name else None
    gear_pack_json = _build_starting_gear_pack(
        profession=profession,
        era=era,
    )

    character = Character(
        session_id=session.id,
        name=_default_name(race, profession),
        race_id=race.id if race else None,
        profession_id=profession.id if profession else None,
        training_id=training.id if training else None,
        level=level,
        attributes_json={
            "scores": attributes,
            "derived": derived,
            "pending": pending or None,
        },
        skill_levels_json=None,
        gear_pack_json=gear_pack_json,
        statuses_json={},
    )
    db.add(character)
    db.flush()
    return character


def _default_name(race: Race | None, profession: Profession | None) -> str:
    if race and profession:
        return f"{race.name} {profession.name}"
    if race:
        return race.name
    if profession:
        return profession.name
    return "Adventurer"


def _get_by_name(db: Session, model, name: str) -> Any | None:
    return db.query(model).filter(func.lower(model.name) == name.lower()).first()


def _get_or_create_race(db: Session, name: str) -> Race:
    record = _get_by_name(db, Race, name)
    if record:
        return record
    record = Race(
        name=name,
        description="Auto-created placeholder race.",
        attributes_json={},
    )
    db.add(record)
    db.flush()
    return record


def _get_or_create_profession(db: Session, name: str) -> Profession:
    record = _get_by_name(db, Profession, name)
    if record:
        return record
    record = Profession(
        name=name,
        description="Auto-created placeholder profession.",
        attributes_json={"startingCredits": 0},
        gear_pack_json={},
    )
    db.add(record)
    db.flush()
    return record


def _get_or_create_training(db: Session, name: str) -> Training:
    record = _get_by_name(db, Training, name)
    if record:
        return record
    record = Training(
        name=name,
        description="Auto-created placeholder training.",
        skill_levels_json={},
    )
    db.add(record)
    db.flush()
    return record


def _compute_attributes(
    race: Race | None,
    profession: Profession | None,
    training: Training | None,
) -> tuple[dict, dict]:
    attributes = {key: 0 for key in ATTRIBUTE_KEYS}
    pending: dict[str, Any] = {}

    for source in (race, profession, training):
        if not source:
            continue
        bonuses = _extract_attribute_bonus(source)
        if bonuses:
            pending.update(_apply_attribute_bonus(attributes, bonuses))

    return attributes, pending


def _extract_attribute_bonus(source: Any) -> dict | None:
    payload = getattr(source, "attributes_json", None) or getattr(
        source, "skill_levels_json", None
    )
    if not isinstance(payload, dict):
        return None
    bonus = payload.get("attributeBonus") or payload.get("attribute_bonus")
    if isinstance(bonus, dict):
        return bonus
    return None


def _apply_attribute_bonus(attributes: dict, bonus: dict) -> dict:
    pending: dict[str, Any] = {}
    for key, value in bonus.items():
        normalized = ATTRIBUTE_ALIASES.get(str(key).lower())
        if normalized and isinstance(value, (int, float)):
            attributes[normalized] += int(value)
        else:
            pending[key] = value
    return pending


def _compute_derived_stats(
    attributes: dict,
    training: Training | None,
    leveling: Leveling | None,
    *,
    armor_value: int | None,
) -> dict:
    training_data = training.skill_levels_json if training else {}
    if not isinstance(training_data, dict):
        training_data = {}

    training_hp = _safe_int(training_data.get("hitPoints"))
    training_initiative = _safe_int(training_data.get("initiative"))
    training_armor = _safe_int(training_data.get("armorRating"))

    leveling_data = leveling.attributes_json if leveling else {}
    if not isinstance(leveling_data, dict):
        leveling_data = {}

    hp_bonus = 1 if leveling_data.get("hp") is True else 0
    con_score = attributes.get("CON", 0)

    resolved_armor = armor_value
    if resolved_armor is None and training_armor is not None:
        resolved_armor = training_armor - 10 if training_armor >= 10 else training_armor
    if resolved_armor is None:
        resolved_armor = 0

    return {
        "hp": con_score + (training_hp or 0) + hp_bonus,
        "armor_rating": 10 + attributes.get("DEX", 0) + resolved_armor,
        "initiative_bonus": attributes.get("DEX", 0) + (training_initiative or 0),
    }


def _build_starting_gear_pack(
    *,
    profession: Profession | None,
    era: Era | None,
) -> dict:
    gear: dict[str, Any] = {}

    starting_credits = None
    if profession and isinstance(profession.attributes_json, dict):
        starting_credits = profession.attributes_json.get("startingCredits")
        if starting_credits is None:
            starting_credits = profession.attributes_json.get("starting_credits")

    if starting_credits is not None:
        gear["starting_credits"] = starting_credits
        gear.setdefault("credits", starting_credits)

    gear_packs = _extract_gear_packs(era.profile_json if era else None)
    patch_packs = _extract_gear_packs(era.patch_json if era else None)
    if isinstance(gear_packs, dict) and isinstance(patch_packs, dict):
        merged = dict(gear_packs)
        merged.update(patch_packs)
        gear_packs = merged
    elif patch_packs:
        gear_packs = patch_packs

    if gear_packs is not None:
        gear["gear_packs"] = gear_packs

    return gear or {}


def _extract_gear_packs(payload: dict | None) -> Any | None:
    if not isinstance(payload, dict):
        return None
    for key in ("gear_packs", "gearPacks", "starting_gear", "gear"):
        if key in payload:
            return payload.get(key)
    return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _default_tone_prefs(metadata: dict) -> dict:
    prefs = metadata.get("player_prefs")
    if isinstance(prefs, dict):
        return {
            "violence_level": prefs.get("violence_level"),
            "horror_level": prefs.get("horror_level") or prefs.get("horror"),
        }
    return {"violence_level": None, "horror_level": None}


def _default_themes(metadata: dict) -> dict:
    prefs = metadata.get("player_prefs")
    if isinstance(prefs, dict):
        return {"avoid": prefs.get("avoid") or []}
    return {"avoid": []}


def _default_pacing(metadata: dict) -> dict:
    return {"pace": "balanced"}


def _default_challenge(metadata: dict) -> dict:
    return {"level": "standard"}


def _default_boundaries(metadata: dict) -> dict:
    return {"lines": [], "veils": []}


def _default_interest_weights() -> dict:
    categories = [
        "combat",
        "crafting",
        "mystery",
        "politics",
        "horror",
        "exploration",
    ]
    return {name: {"count": 0, "weight": 0.0} for name in categories}


def _build_default_scene(*, era_name: str, location_name: str | None) -> dict:
    location = location_name or "unknown location"
    slug = _slugify(location)
    return {
        "scene_id": f"{slug}_entrance",
        "location_id": slug,
        "summary": f"You are at the entrance of {location}.",
        "active_threats": [],
        "npcs_present": [],
        "open_hooks": ["Why this place matters", "Who sent you"],
        "established": True,
    }


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "scene"


def respawn_character(character: Character) -> Character:
    attributes = character.attributes_json or {}
    derived = attributes.get("derived") if isinstance(attributes, dict) else None
    if not isinstance(derived, dict):
        derived = {}

    current_hp = derived.get("hp")
    if current_hp is None or current_hp <= 0:
        derived["hp"] = max(1, int(current_hp or 0))
    attributes["derived"] = derived

    resources = attributes.get("resources") if isinstance(attributes, dict) else None
    if not isinstance(resources, dict):
        resources = {}
    defaults = base_actions()
    resources["actions"] = defaults["actions"]
    resources["reactions"] = defaults["reactions"]
    attributes["resources"] = resources

    character.attributes_json = attributes
    character.statuses_json = {}
    return character
