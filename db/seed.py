import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path = [path for path in sys.path if Path(path).resolve() != SCRIPT_DIR]

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from db import SessionLocal  # noqa: E402
from models import (  # noqa: E402
    ArmorBase,
    Era,
    Leveling,
    Profession,
    Race,
    Skill,
    Status,
    SuperPower,
    Training,
    WeaponBase,
)

JSON_DIR = REPO_ROOT / "docs" / "jsons"


def load_json(file_name: str) -> Any | None:
    path = JSON_DIR / file_name
    if not path.exists():
        print(f"Missing {path}, skipping.")
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def strip_fields(payload: dict, *keys: str) -> dict:
    data = dict(payload)
    for key in keys:
        data.pop(key, None)
    return data


def upsert_by_name(session, model, name: str, **fields: Any) -> None:
    exists = session.query(model).filter_by(name=name).first()
    if exists:
        return
    session.add(model(name=name, **fields))


def seed_races(session) -> None:
    data = load_json("races.json")
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict) or "name" not in item:
            continue
        attributes = strip_fields(item, "name", "description")
        upsert_by_name(
            session,
            Race,
            item["name"],
            description=item.get("description"),
            attributes_json=attributes or None,
        )


def seed_professions(session) -> None:
    data = load_json("professions.json")
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict) or "name" not in item:
            continue
        attributes = strip_fields(item, "name", "description")
        upsert_by_name(
            session,
            Profession,
            item["name"],
            description=item.get("description"),
            attributes_json=attributes or None,
        )


def seed_skills(session) -> None:
    data = load_json("skills.json")
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict) or "name" not in item:
            continue
        definition = strip_fields(item, "name", "description")
        upsert_by_name(
            session,
            Skill,
            item["name"],
            description=item.get("description"),
            definition_json=definition or None,
        )


def seed_trainings(session) -> None:
    data = load_json("trainings.json")
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict) or "name" not in item:
            continue
        details = strip_fields(item, "name", "description")
        upsert_by_name(
            session,
            Training,
            item["name"],
            description=item.get("description"),
            skill_levels_json=details or None,
        )


def seed_leveling(session) -> None:
    data = load_json("leveling.json")
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict) or "level" not in item:
            continue
        level = item["level"]
        exists = session.query(Leveling).filter_by(level=level).first()
        if exists:
            continue
        details = strip_fields(item, "level", "description")
        session.add(
            Leveling(
                level=level,
                description=item.get("description"),
                attributes_json=details or None,
                skill_levels_json=None,
            )
        )


def seed_statuses(session) -> None:
    data = load_json("statuses.json")
    if not isinstance(data, dict):
        return
    for key, payload in data.items():
        if not isinstance(payload, dict):
            continue
        description = payload.get("description")
        progression = strip_fields(payload, "description")
        upsert_by_name(
            session,
            Status,
            key,
            description=description,
            progression_json=progression or None,
        )


def extract_era_payload(item: dict) -> tuple[dict | None, dict | None]:
    profile = item.get("base") or item.get("profile")
    if profile is None:
        base_skills = item.get("base_skills")
        base_professions = item.get("base_professions")
        if base_skills or base_professions:
            profile = {
                "skills": base_skills,
                "professions": base_professions,
            }

    patches = item.get("patches") or item.get("patch") or item.get("overrides")
    if patches is None:
        patch_skills = item.get("skill_overrides")
        patch_professions = item.get("profession_overrides")
        if patch_skills or patch_professions:
            patches = {
                "skills": patch_skills,
                "professions": patch_professions,
            }

    return profile, patches


def seed_eras(session) -> None:
    data = load_json("eras.json")
    if not data:
        return
    items = data if isinstance(data, list) else data.get("eras")
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id")
        if not name:
            continue
        profile_json, patch_json = extract_era_payload(item)
        upsert_by_name(
            session,
            Era,
            name,
            description=item.get("description"),
            profile_json=profile_json,
            patch_json=patch_json,
        )


def seed_armor(session) -> None:
    data = load_json("armor.json")
    if not isinstance(data, dict):
        return
    for payload in data.values():
        if not isinstance(payload, dict):
            continue
        name = payload.get("name")
        if not name:
            continue
        upsert_by_name(
            session,
            ArmorBase,
            name,
            armor_rating=payload.get("armorRating"),
            stats_json=payload,
        )


def seed_weapons(session) -> None:
    data = load_json("weapons.json")
    if not isinstance(data, dict):
        return
    for payload in data.values():
        if not isinstance(payload, dict):
            continue
        name = payload.get("name")
        if not name:
            continue
        upsert_by_name(
            session,
            WeaponBase,
            name,
            damage=payload.get("damage"),
            damage_type=payload.get("damageType"),
            stats_json=payload,
        )


def seed_super_powers(session) -> None:
    for file_name in (
        "sherlock.json",
        "teleportation.json",
        "power_drain.json",
        "superspeed.json",
    ):
        payload = load_json(file_name)
        if not isinstance(payload, dict):
            continue
        name = payload.get("school") or payload.get("name")
        if not name:
            name = Path(file_name).stem.replace("_", " ").title()
        upsert_by_name(
            session,
            SuperPower,
            name,
            description=payload.get("description"),
            definition_json=payload,
        )


def main() -> None:
    with SessionLocal() as session:
        seed_races(session)
        seed_professions(session)
        seed_skills(session)
        seed_trainings(session)
        seed_leveling(session)
        seed_statuses(session)
        seed_eras(session)
        seed_armor(session)
        seed_weapons(session)
        seed_super_powers(session)
        session.commit()


if __name__ == "__main__":
    main()
