from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from typing import Any

from db import SessionLocal
from models import Clock, PlayerProfile, Session as SessionModel, Thread


EVENTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "..",
    "docs",
    "jsons",
    "events.json",
)


@dataclass(frozen=True)
class DirectorResult:
    thread_id: int | None
    event: dict | None
    clocks_advanced: int


def director_tick(session_id: int, reason: str) -> DirectorResult:
    with SessionLocal() as db:
        session = db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found.")
        profile = (
            db.query(PlayerProfile)
            .filter(PlayerProfile.session_id == session_id)
            .first()
        )

        metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
        director_index = int(metadata.get("director_index", 0))
        metadata["director_index"] = director_index + 1
        session.metadata_json = metadata

        steps = _steps_for_reason(reason, metadata)
        clocks = (
            db.query(Clock)
            .filter(Clock.session_id == session_id)
            .order_by(Clock.id.asc())
            .all()
        )
        clocks_advanced = _advance_clocks(clocks, steps)

        event = _pick_event(session.rng_seed or 0, director_index, metadata, profile)
        thread_type = _map_event_type(event.get("type") if event else None)
        thread = Thread(
            session_id=session_id,
            type=thread_type,
            status="open",
            urgency=_map_urgency(thread_type),
            visibility="player",
            related_entities_json={},
            text=event.get("text") if event else "A quiet moment settles in.",
        )
        metadata["last_hook_type"] = event.get("type") if event else None
        session.metadata_json = metadata
        db.add(thread)
        db.commit()
        db.refresh(thread)
        return DirectorResult(
            thread_id=thread.id,
            event=event,
            clocks_advanced=clocks_advanced,
        )


def _steps_for_reason(reason: str, metadata: dict) -> int:
    reason_key = reason.strip().lower()
    steps_map = {
        "rest": 1,
        "travel": 2,
        "downtime": 3,
        "turn": 1,
    }
    if reason_key == "every_n_turns":
        return int(metadata.get("director_every_n", 3))
    return steps_map.get(reason_key, 1)


def _advance_clocks(clocks: list[Clock], steps: int) -> int:
    for clock in clocks:
        if clock.steps_done >= clock.steps_total:
            continue
        clock.steps_done = min(clock.steps_total, clock.steps_done + steps)
    return steps


def _pick_event(
    seed: int,
    director_index: int,
    metadata: dict,
    profile: PlayerProfile | None,
) -> dict:
    events = _load_events()
    if not events:
        return {"type": "calm_moment", "text": "A quiet beat settles over the scene."}
    last_type = metadata.get("last_hook_type")
    weights = _compute_event_weights(events, profile, last_type)
    rng = random.Random(seed + director_index)
    return _weighted_choice(events, weights, rng)


def _compute_event_weights(
    events: list[dict],
    profile: PlayerProfile | None,
    last_type: str | None,
) -> list[float]:
    interest_weights = _extract_interest_weights(profile)
    avoid = _extract_avoid_themes(profile)
    weights: list[float] = []
    for event in events:
        event_type = event.get("type")
        weight = 1.0 + _event_interest_weight(event_type, interest_weights)
        if _is_avoided(event_type, avoid):
            weight = 0.0
        if last_type and event_type == last_type:
            weight *= 0.3
        weights.append(weight)
    if any(weight > 0 for weight in weights):
        return weights
    return [1.0 for _ in events]


def _weighted_choice(events: list[dict], weights: list[float], rng: random.Random) -> dict:
    if not events:
        return {}
    max_weight = max(weights) if weights else 0.0
    if max_weight <= 0:
        return rng.choice(events)
    candidates = [
        event for event, weight in zip(events, weights) if weight == max_weight
    ]
    if len(candidates) == 1:
        return candidates[0]
    return rng.choice(candidates)


def _extract_interest_weights(profile: PlayerProfile | None) -> dict:
    if profile is None:
        return {}
    data = profile.interests_json
    if isinstance(data, dict):
        return data
    return {}


def _extract_avoid_themes(profile: PlayerProfile | None) -> set[str]:
    if profile is None:
        return set()
    themes = profile.themes_json
    if isinstance(themes, dict):
        avoid = themes.get("avoid")
        if isinstance(avoid, list):
            return {str(item).strip().lower() for item in avoid if str(item).strip()}
    return set()


def _event_interest_weight(event_type: str | None, interests: dict) -> float:
    mapping = {
        "ambush": "combat",
        "rumor": "mystery",
        "messenger_arrives": "politics",
        "new_hook": "exploration",
        "calm_moment": "crafting",
    }
    category = mapping.get(event_type or "")
    if not category:
        return 0.0
    entry = interests.get(category)
    if not isinstance(entry, dict):
        return 0.0
    value = entry.get("weight")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_avoided(event_type: str | None, avoid: set[str]) -> bool:
    mapping = {
        "ambush": {"combat", "violence", "horror"},
        "rumor": {"mystery"},
        "messenger_arrives": {"politics"},
        "new_hook": {"exploration"},
        "calm_moment": {"crafting"},
    }
    for theme in mapping.get(event_type or "", set()):
        if theme in avoid:
            return True
    return False


def _map_event_type(value: str | None) -> str:
    mapping = {
        "new_hook": "hook",
        "messenger_arrives": "hook",
        "rumor": "rumor",
        "ambush": "consequence",
        "calm_moment": "foreshadow",
    }
    return mapping.get(value or "", "hook")


def _map_urgency(thread_type: str) -> str:
    return "high" if thread_type == "consequence" else "med"


def _load_events() -> list[dict]:
    try:
        with open(EVENTS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []
