from __future__ import annotations

from typing import Any


def effective_era_profile(era: Any) -> dict:
    if era is None:
        return {}
    base, patch = _extract_profiles(era)
    return _deep_merge(base or {}, patch or {})


def get_skill_for_era(skill_name: str, era: Any) -> str:
    if not skill_name:
        return skill_name
    effective = effective_era_profile(era)
    aliases = _extract_skill_aliases(effective)
    key = skill_name.strip().lower()
    mapped = aliases.get(key)
    if mapped:
        return mapped
    return skill_name


def get_skill_aliases(era: Any) -> dict[str, str]:
    effective = effective_era_profile(era)
    return _extract_skill_aliases(effective)


def apply_cost_modifier(cost: int, era: Any) -> int:
    if cost < 0:
        return cost
    effective = effective_era_profile(era)
    multiplier = _extract_cost_multiplier(effective)
    if multiplier is None:
        return cost
    return max(0, int(round(cost * multiplier)))


def is_gear_category_illegal(category: str, era: Any) -> bool:
    if not category:
        return False
    effective = effective_era_profile(era)
    illegal = _extract_illegal_categories(effective)
    return category.strip().lower() in illegal


def get_illegal_gear_categories(era: Any) -> set[str]:
    effective = effective_era_profile(era)
    return _extract_illegal_categories(effective)


def _extract_profiles(era: Any) -> tuple[dict | None, dict | None]:
    if isinstance(era, dict):
        if "profile_json" in era or "patch_json" in era:
            return era.get("profile_json"), era.get("patch_json")
        if "profile" in era or "patch" in era:
            return era.get("profile"), era.get("patch")
        return era, None
    profile = getattr(era, "profile_json", None)
    patch = getattr(era, "patch_json", None)
    return profile, patch


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _extract_skill_aliases(profile: dict) -> dict[str, str]:
    aliases = {}
    for key in ("skill_aliases", "aliases"):
        value = profile.get(key)
        if isinstance(value, dict):
            for alias, target in value.items():
                if isinstance(target, str):
                    aliases[str(alias).strip().lower()] = target
            if key == "aliases":
                nested = value.get("skills")
                if isinstance(nested, dict):
                    for alias, target in nested.items():
                        if isinstance(target, str):
                            aliases[str(alias).strip().lower()] = target
    return aliases


def _extract_cost_multiplier(profile: dict) -> float | None:
    for key in ("cost_multiplier", "price_multiplier"):
        value = profile.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    scarcity = profile.get("scarcity")
    if isinstance(scarcity, dict):
        value = scarcity.get("cost_multiplier") or scarcity.get("multiplier")
        if isinstance(value, (int, float)):
            return float(value)
    if profile.get("post_scarcity") is True:
        return 0.5
    return None


def _extract_illegal_categories(profile: dict) -> set[str]:
    for key in ("illegal_gear_categories", "restricted_gear_categories"):
        value = profile.get(key)
        if isinstance(value, list):
            return {str(item).strip().lower() for item in value}
        if isinstance(value, str):
            return {value.strip().lower()}
    return set()
