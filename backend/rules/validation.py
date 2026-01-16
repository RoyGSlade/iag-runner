from __future__ import annotations

from typing import Iterable


class ValidationError(ValueError):
    pass


def _normalize_era(era_name: str | None) -> str:
    if not era_name:
        return ""
    return era_name.strip().lower()


def _has_gun_tag(tags: Iterable[str] | None) -> bool:
    if not tags:
        return False
    return any(tag.strip().lower() in {"gun", "firearm"} for tag in tags)


def _allow_guns_in_medieval(era_patch: dict | None) -> bool:
    if not isinstance(era_patch, dict):
        return False

    direct = era_patch.get("allow_guns")
    if isinstance(direct, bool):
        return direct
    direct = era_patch.get("gun_allowed")
    if isinstance(direct, bool):
        return direct

    weapons = era_patch.get("weapons")
    if isinstance(weapons, dict):
        nested = weapons.get("allow_guns")
        if isinstance(nested, bool):
            return nested
        nested = weapons.get("gun_allowed")
        if isinstance(nested, bool):
            return nested

    restrictions = era_patch.get("restrictions")
    if isinstance(restrictions, dict):
        value = restrictions.get("guns")
        if isinstance(value, str):
            return value.strip().lower() == "allow"

    return False


def validate_weapon_allowed(
    era_name: str | None,
    weapon_tags: Iterable[str] | None,
    era_patch: dict | None = None,
) -> None:
    if not _has_gun_tag(weapon_tags):
        return

    era = _normalize_era(era_name)
    if era == "prehistoric":
        raise ValidationError("Guns are not allowed in the Prehistoric era.")
    if era == "medieval":
        if _allow_guns_in_medieval(era_patch):
            return
        raise ValidationError(
            "Guns are not allowed in the Medieval era without an era patch."
        )
