from __future__ import annotations

import random

CANONICAL_TYPES: dict[str, set[str]] = {
    "frontier town": {"frontier town", "frontier", "town", "frontier-town"},
    "megacity": {"megacity", "mega city", "mega-city", "metro", "city"},
    "mining outpost": {"mining outpost", "mining", "outpost", "mining-outpost"},
    "moonbase": {"moonbase", "moon base", "lunar base"},
    "jungle ruin": {"jungle ruin", "jungle", "ruin", "jungle-ruin"},
    "desert highway": {"desert highway", "desert", "highway"},
    "floating arcology": {"floating arcology", "arcology", "floating"},
    "undersea habitat": {"undersea habitat", "undersea", "sea base", "aquatic"},
    "space station": {"space station", "station", "orbital"},
    "other": {"other", "custom"},
}

DEFAULT_TYPE_BY_ERA = {
    "prehistoric": "jungle ruin",
    "medieval": "frontier town",
    "colonial": "frontier town",
    "modern": "megacity",
    "space": "space station",
}

ERA_PREFIXES = {
    "prehistoric": ["Stone", "Amber", "Wild", "Sun", "Echo"],
    "medieval": ["Iron", "Crown", "Mist", "Ebon", "Silver"],
    "colonial": ["Frontier", "Harbor", "Union", "Liberty", "Foundry"],
    "modern": ["Metro", "Central", "Bright", "Neon", "Axis"],
    "space": ["Nova", "Vega", "Aurora", "Helix", "Orion"],
}

TYPE_SUFFIXES = {
    "frontier town": ["Gulch", "Crossing", "Fork", "Hollow", "Ridge"],
    "megacity": ["Sprawl", "Metroplex", "Sector", "Stack", "District"],
    "mining outpost": ["Pit", "Claim", "Shaft", "Quarry", "Outpost"],
    "moonbase": ["Crater", "Luna Base", "Moonpost", "Lunar Hold", "Dustworks"],
    "jungle ruin": ["Ruin", "Temple", "Vault", "Sanctum", "Ziggurat"],
    "desert highway": ["Trace", "Run", "Line", "Causeway", "Trail"],
    "floating arcology": ["Arcology", "Skyhold", "Spire", "Aerie", "Drift"],
    "undersea habitat": ["Habitat", "Trench", "Atoll", "Deep", "Nexus"],
    "space station": ["Station", "Ring", "Spindle", "Dock", "Platform"],
    "other": ["Outpost", "Haven", "Nexus", "Hold", "Site"],
}


def normalize_setting_type(value: str | None, *, era_name: str | None = None) -> str:
    if value:
        cleaned = str(value).strip().lower().replace("_", " ").replace("-", " ")
        cleaned = " ".join(cleaned.split())
        for canonical, synonyms in CANONICAL_TYPES.items():
            if cleaned == canonical or cleaned in synonyms:
                return canonical
    if era_name:
        fallback = DEFAULT_TYPE_BY_ERA.get(era_name.strip().lower())
        if fallback:
            return fallback
    return "other"


def generate_location_name(
    *,
    era_name: str | None,
    setting_type: str | None,
    seed: int | None,
) -> str:
    rng = random.Random(seed)
    era_key = (era_name or "").strip().lower()
    prefix_pool = ERA_PREFIXES.get(era_key, ["Anchor", "Drift", "Cross", "Prime"])
    normalized_type = normalize_setting_type(setting_type, era_name=era_name)
    suffix_pool = TYPE_SUFFIXES.get(normalized_type, TYPE_SUFFIXES["other"])
    prefix = rng.choice(prefix_pool)
    suffix = rng.choice(suffix_pool)
    return f"{prefix} {suffix}"
