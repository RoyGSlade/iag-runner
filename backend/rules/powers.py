from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rules.statuses import apply_status

POWER_FILES = {
    "Sherlock": "sherlock.json",
    "Teleportation": "teleportation.json",
    "Power Drain": "power_drain.json",
    "Superspeed": "superspeed.json",
}

POWER_EFFECTS = {
    "sherlock.scanning_gaze": {
        "type": "status",
        "status": "Concentration",
        "duration": 1,
    },
    "teleportation.vanish": {
        "type": "status",
        "status": "Hidden",
        "duration": 1,
    },
    "power_drain.reserve": {
        "type": "resource",
        "resource": "reserve_charges",
        "delta": 1,
    },
    "superspeed.time_dilation": {
        "type": "resource",
        "resource": "extra_actions",
        "delta": 2,
    },
}


class PowerError(ValueError):
    pass


@dataclass(frozen=True)
class PowerDefinition:
    power_id: str
    name: str
    school: str
    level: int | None
    activation_cost: str | None
    duration: str | None
    range: str | None
    uses: str | None
    description: str | None
    effect: dict[str, Any]


@dataclass
class PowerUseResult:
    power: PowerDefinition
    effect: dict[str, Any]
    updated_statuses: dict[str, Any]
    updated_attributes: dict[str, Any]


_CATALOG: dict[str, PowerDefinition] | None = None


def load_power_catalog() -> dict[str, PowerDefinition]:
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG

    repo_root = Path(__file__).resolve().parents[2]
    json_dir = repo_root / "docs" / "jsons"
    catalog: dict[str, PowerDefinition] = {}

    for school_name, file_name in POWER_FILES.items():
        path = json_dir / file_name
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        school = payload.get("school") or school_name
        powers = payload.get("powers", {})
        if not isinstance(powers, dict):
            continue
        for power_id, data in powers.items():
            if not isinstance(data, dict):
                continue
            effect = POWER_EFFECTS.get(power_id, {"type": "none"})
            catalog[power_id] = PowerDefinition(
                power_id=power_id,
                name=data.get("name") or power_id,
                school=school,
                level=data.get("level"),
                activation_cost=data.get("activationCost"),
                duration=data.get("duration"),
                range=data.get("range"),
                uses=data.get("uses"),
                description=data.get("description"),
                effect=effect,
            )

    _CATALOG = catalog
    return catalog


def get_power_definition(power_id: str) -> PowerDefinition:
    catalog = load_power_catalog()
    if power_id in catalog:
        return catalog[power_id]
    raise PowerError(f"Unknown power: {power_id}")


def use_power(era_name: str, character: Any, power_id: str) -> PowerUseResult:
    if era_name.strip().lower() != "space":
        raise PowerError("Powers are locked outside the Space era.")

    power = get_power_definition(power_id)
    if not _has_power_unlocked(character, power):
        raise PowerError("Power is not unlocked for this character.")

    effect = power.effect
    updated_statuses = _apply_effect_to_statuses(
        character.statuses_json or {},
        effect,
    )
    updated_attributes = _apply_effect_to_attributes(
        character.attributes_json or {},
        effect,
    )

    character.statuses_json = updated_statuses
    character.attributes_json = updated_attributes

    return PowerUseResult(
        power=power,
        effect=effect,
        updated_statuses=updated_statuses,
        updated_attributes=updated_attributes,
    )


def _has_power_unlocked(character: Any, power: PowerDefinition) -> bool:
    data = character.attributes_json or {}
    unlocked_powers = _extract_power_list(data)
    if power.power_id in unlocked_powers:
        return True

    unlocked_schools = _extract_school_list(data)
    return power.school.lower() in unlocked_schools


def _extract_power_list(data: dict) -> set[str]:
    for key in ("powers_unlocked", "powers", "unlocked_powers"):
        value = data.get(key)
        if isinstance(value, list):
            return {str(item) for item in value}
        if isinstance(value, dict):
            return {str(name) for name, enabled in value.items() if enabled}
        if isinstance(value, str):
            return {value}
    return set()


def _extract_school_list(data: dict) -> set[str]:
    for key in ("power_schools", "schools"):
        value = data.get(key)
        if isinstance(value, list):
            return {str(item).lower() for item in value}
        if isinstance(value, str):
            return {value.lower()}
    return set()


def _apply_effect_to_statuses(statuses: dict, effect: dict[str, Any]) -> dict:
    if effect.get("type") != "status":
        return statuses
    return apply_status(
        statuses,
        effect.get("status", ""),
        duration=effect.get("duration"),
        level=effect.get("level", 1),
        stacks=effect.get("stacks", 1),
    )


def _apply_effect_to_attributes(attributes: dict, effect: dict[str, Any]) -> dict:
    if effect.get("type") != "resource":
        return attributes
    updated = dict(attributes)
    resources = updated.get("resources")
    if not isinstance(resources, dict):
        resources = {}
    key = str(effect.get("resource"))
    delta = int(effect.get("delta", 0))
    resources[key] = int(resources.get(key, 0)) + delta
    updated["resources"] = resources
    return updated
