from __future__ import annotations

import copy
from typing import Any

STATUS_CANONICAL = {
    "bleeding": "Bleeding",
    "ignited": "Ignited",
    "stun": "Stun",
    "asphyxiation": "Asphyxiation",
    "toxin": "Toxin",
    "injured": "Injured",
    "concentration": "Concentration",
    "hidden": "Hidden",
    "cold": "Cold",
    "disease": "Disease",
}

DEFAULT_DURATIONS = {
    "Bleeding": 3,
    "Ignited": 3,
    "Stun": 1,
    "Asphyxiation": 2,
    "Toxin": 3,
    "Injured": 3,
    "Concentration": None,
    "Hidden": 1,
    "Cold": 3,
    "Disease": None,
}


def normalize_status(name: str) -> str:
    key = name.strip().lower()
    if key in STATUS_CANONICAL:
        return STATUS_CANONICAL[key]
    raise ValueError(f"Unknown status: {name}")


def apply_status(
    statuses: dict | None,
    name: str,
    *,
    stacks: int = 1,
    level: int = 1,
    duration: int | None = None,
) -> dict:
    canonical = normalize_status(name)
    updated = copy.deepcopy(statuses or {})
    entry = updated.get(canonical, {"stacks": 0, "level": 0, "duration": None})

    entry["stacks"] = max(1, int(entry.get("stacks", 0)) + int(stacks))
    entry["level"] = max(int(entry.get("level", 0)), int(level))

    if duration is None:
        duration = DEFAULT_DURATIONS.get(canonical)
    if duration is not None:
        existing = entry.get("duration")
        if existing is None:
            entry["duration"] = int(duration)
        else:
            entry["duration"] = max(int(existing), int(duration))

    updated[canonical] = entry
    return updated


def ramp_status(
    statuses: dict | None,
    name: str,
    *,
    trigger: str,
    amount: int = 1,
) -> dict:
    canonical = normalize_status(name)
    updated = copy.deepcopy(statuses or {})
    entry = updated.get(canonical, {"stacks": 1, "level": 1, "duration": None})

    trigger_key = trigger.strip().lower()
    if canonical == "Bleeding" and trigger_key == "move":
        entry["stacks"] = int(entry.get("stacks", 1)) + amount
        entry["level"] = max(int(entry.get("level", 1)), entry["stacks"])
        entry["duration"] = max(int(entry.get("duration") or 0), 3)
    elif canonical == "Ignited" and trigger_key in {"ignite", "fuel"}:
        entry["level"] = int(entry.get("level", 1)) + amount
        entry["duration"] = max(int(entry.get("duration") or 0), 3)
    elif canonical == "Cold" and trigger_key in {"cold", "exposure"}:
        entry["level"] = int(entry.get("level", 1)) + amount
        entry["duration"] = max(int(entry.get("duration") or 0), 3)
    elif canonical == "Disease" and trigger_key == "day":
        entry["level"] = int(entry.get("level", 1)) + amount
    elif canonical == "Asphyxiation" and trigger_key == "no_air":
        entry["level"] = int(entry.get("level", 1)) + amount
        entry["duration"] = max(int(entry.get("duration") or 0), 2)
    elif canonical == "Toxin" and trigger_key in {"exposed", "dose"}:
        entry["level"] = int(entry.get("level", 1)) + amount
        entry["duration"] = max(int(entry.get("duration") or 0), 3)
    elif canonical == "Injured" and trigger_key in {"worsen", "hit"}:
        entry["level"] = int(entry.get("level", 1)) + amount
        entry["duration"] = max(int(entry.get("duration") or 0), 3)
    elif canonical in {"Hidden", "Concentration", "Stun"} and trigger_key == "refresh":
        duration = DEFAULT_DURATIONS.get(canonical)
        if duration is not None:
            entry["duration"] = max(int(entry.get("duration") or 0), duration)

    updated[canonical] = entry
    return updated


def tick_statuses(
    statuses: dict | None,
    *,
    tick_type: str = "turn",
) -> tuple[dict, int, list[str]]:
    updated = copy.deepcopy(statuses or {})
    hp_delta = 0
    expired: list[str] = []
    tick_key = tick_type.strip().lower()

    for name, entry in list(updated.items()):
        canonical = normalize_status(name)
        entry = dict(entry)
        stacks = int(entry.get("stacks", 1))
        level = int(entry.get("level", 1))

        if canonical == "Bleeding" and tick_key == "turn":
            hp_delta -= max(1, stacks) * max(1, level)
        elif canonical == "Ignited" and tick_key == "turn":
            hp_delta -= 2 * max(1, level)
        elif canonical == "Asphyxiation" and tick_key == "turn":
            hp_delta -= 2 * max(1, level)
        elif canonical == "Toxin" and tick_key == "turn":
            hp_delta -= max(1, level)
        elif canonical == "Disease" and tick_key == "day":
            level = max(1, level) + 1
            entry["level"] = level
            hp_delta -= level

        duration = entry.get("duration")
        if duration is not None and tick_key == "turn":
            duration = int(duration) - 1
            if duration <= 0:
                expired.append(canonical)
                updated.pop(canonical, None)
                continue
            entry["duration"] = duration

        updated[canonical] = entry

    return updated, hp_delta, expired


def total_dex_penalty(statuses: dict | None) -> int:
    if not isinstance(statuses, dict):
        return 0
    penalty = 0
    for name, entry in statuses.items():
        canonical = normalize_status(name)
        level = int(entry.get("level", 1))
        if canonical == "Cold":
            penalty += max(1, level)
    return penalty


def status_snapshot(statuses: dict | None) -> dict[str, Any]:
    return copy.deepcopy(statuses or {})
