from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from db import SessionLocal
from models import (
    Character,
    Clock,
    Discovery,
    PlayerProfile,
    Project,
    Ruling,
    Session as SessionModel,
    SystemDraft,
    Thread,
)
from gm_os.memory import promote_memories_for_session
from gm_os.protocols import ProtocolId
from gm_os.router import route_envelope
from gm_os.schemas import SystemDraft as SystemDraftSchema
from llm.client import OllamaClient
from llm.schemas import Intent, NarrationRequest
from rules.combat import base_actions
from rules.core import SessionState, roll, roll_d20


class TurnError(ValueError):
    pass


@dataclass
class TurnIntent:
    action: str
    target_ar: int = 10
    weapon_damage: str = "1d6"
    skill_bonus: int = 0
    attr_bonus: int = 0
    actions_required: int = 1
    power_id: str | None = None
    item_used: str | None = None
    movement: dict | None = None
    target_label: str | None = None


@dataclass
class TurnResult:
    intent: dict
    rolls: list[dict]
    outcome: dict
    state_diff: dict
    narration_prompt_context: dict
    narration: str
    suggested_actions: list[dict]
    needs_clarification: bool
    clarification_question: str | None
    clarification_questions: list[str]
    project_created: dict | None
    raw_llm_output: str | None
    parsed_intent: dict | None
    validation_errors: list[str]


def execute_turn(
    session_id: int,
    player_text: str | None,
    *,
    action_type: str | None = None,
    payload: dict | None = None,
) -> TurnResult:
    with SessionLocal() as db:
        session = db.get(SessionModel, session_id)
        if session is None:
            raise TurnError("Session not found.")
        character = (
            db.query(Character).filter(Character.session_id == session_id).first()
        )
        if character is None:
            raise TurnError("Character not found.")
        threads = (
            db.query(Thread)
            .filter(Thread.session_id == session_id)
            .order_by(Thread.id.asc())
            .all()
        )
        clocks = (
            db.query(Clock)
            .filter(Clock.session_id == session_id)
            .order_by(Clock.id.asc())
            .all()
        )
        intent_override = None
        if action_type:
            data = dict(payload or {})
            data.setdefault("targets", [])
            data["action_type"] = action_type
            intent_override = Intent.model_validate(data)
        def _create_project(payload: dict) -> dict:
            project = Project(
                session_id=payload.get("session_id"),
                character_id=payload.get("character_id"),
                name=payload.get("name") or "Project",
                type=payload.get("type") or "craft",
                requirements_json=payload.get("requirements"),
                constraints_json=payload.get("constraints"),
                work_units_total=payload.get("work_units_total") or 1,
                work_units_done=payload.get("work_units_done") or 0,
                status=payload.get("status") or "active",
            )
            db.add(project)
            db.flush()
            return {
                "id": project.id,
                "session_id": project.session_id,
                "character_id": project.character_id,
                "name": project.name,
                "type": project.type,
                "requirements": project.requirements_json,
                "constraints": project.constraints_json,
                "work_units_total": project.work_units_total,
                "work_units_done": project.work_units_done,
                "status": project.status,
            }
        def _create_system_draft(payload: dict) -> dict:
            draft = SystemDraft(
                session_id=payload.get("session_id"),
                name=payload.get("name") or "System Draft",
                inputs_json=payload.get("inputs"),
                process_json=payload.get("process"),
                outputs_json=payload.get("outputs"),
                costs_json=payload.get("costs"),
                risks_json=payload.get("risks"),
                checks_json=payload.get("checks"),
            )
            db.add(draft)
            db.flush()
            return {
                "id": draft.id,
                "session_id": draft.session_id,
                "name": draft.name,
                "inputs": draft.inputs_json,
                "process": draft.process_json,
                "outputs": draft.outputs_json,
                "costs": draft.costs_json,
                "risks": draft.risks_json,
                "checks": draft.checks_json,
            }
        def _create_discovery(payload: dict) -> dict:
            discovery = Discovery(
                session_id=payload.get("session_id"),
                gradient=payload.get("gradient") or "partial",
                summary_text=payload.get("summary") or "Discovery noted.",
                tags_json=payload.get("tags"),
                context_json=payload.get("context"),
            )
            db.add(discovery)
            db.flush()
            return {
                "id": discovery.id,
                "session_id": discovery.session_id,
                "gradient": discovery.gradient,
                "summary": discovery.summary_text,
                "tags": discovery.tags_json,
                "context": discovery.context_json,
            }
        def _create_thread(payload: dict) -> dict:
            thread = Thread(
                session_id=payload.get("session_id"),
                type=payload.get("type") or "hook",
                status=payload.get("status") or "open",
                urgency=payload.get("urgency") or "med",
                visibility=payload.get("visibility") or "player",
                related_entities_json=payload.get("related_entities"),
                text=payload.get("text") or "A new lead emerges.",
            )
            db.add(thread)
            db.flush()
            return {
                "id": thread.id,
                "session_id": thread.session_id,
                "type": thread.type,
                "status": thread.status,
                "urgency": thread.urgency,
                "visibility": thread.visibility,
                "related_entities": thread.related_entities_json or {},
                "text": thread.text,
            }
        result = execute_turn_for_state(
            session,
            character,
            player_text or "",
            intent_override=intent_override,
            project_creator=_create_project,
            system_draft_creator=_create_system_draft,
            discovery_creator=_create_discovery,
            thread_creator=_create_thread,
            threads=threads,
            clocks=clocks,
            payload=payload,
        )
        _maybe_store_ruling(db, result.outcome)
        _update_player_profile(db, session, result.intent)
        promote_memories_for_session(db, session, turn_count_threshold=100)
        db.commit()
        db.refresh(session)
        db.refresh(character)
        return result


def execute_turn_for_state(
    session: Any,
    character: Any,
    player_text: str,
    *,
    llm_client: OllamaClient | None = None,
    intent_override: Intent | None = None,
    project_creator: Callable[[dict], dict] | None = None,
    system_draft_creator: Callable[[dict], dict] | None = None,
    discovery_creator: Callable[[dict], dict] | None = None,
    thread_creator: Callable[[dict], dict] | None = None,
    threads: list[Any] | None = None,
    clocks: list[Any] | None = None,
    payload: dict | None = None,
) -> TurnResult:
    llm_client = llm_client or OllamaClient()
    intent_context = _build_intent_context(session, character)
    debug_info: dict = {
        "raw_llm_output": None,
        "parsed_intent": None,
        "validation_errors": [],
    }
    _ensure_scene_state(session)
    if _is_memory_recall_request(player_text):
        return _memory_recall_result(
            session,
            character,
            player_text,
            llm_client,
            intent_context,
            debug_info,
            threads or [],
        )
    if not _has_scene_text(session):
        return _scene_intro_result(
            session,
            character,
            llm_client,
            intent_context,
            debug_info,
        )

    if intent_override:
        intent = intent_override
        debug_info["parsed_intent"] = intent.model_dump()
        return _execute_intent_pipeline(
            session,
            character,
            intent,
            llm_client,
            intent_context,
            debug_info,
            player_text,
        )

    try:
        envelope = llm_client.generate_turn_envelope(
            player_text,
            _build_envelope_context(session, payload),
        )
    except Exception as exc:
        debug_info["validation_errors"].append(str(exc))
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason="Turn envelope could not be generated.",
            ),
            session,
            character,
            _ensure_resources(character.attributes_json),
            llm_client,
            intent_context,
            debug_info,
            clarification_questions=["Could you clarify what you want to do next?"],
        )

    decision = route_envelope(envelope, _build_session_state(session))
    if decision.protocol_id == ProtocolId.PROTO_RETCON_DISPUTE:
        return _retcon_dispute_result(session, character, intent_context, debug_info)
    if decision.protocol_id == ProtocolId.PROTO_RULE_EDGE_CASE:
        return _rule_edge_case_result(
            session,
            character,
            intent_context,
            debug_info,
            player_text,
            envelope,
        )
    if decision.protocol_id == ProtocolId.PROTO_CONTENT_GAP:
        return _content_gap_result(
            session,
            character,
            intent_context,
            debug_info,
            player_text,
            envelope,
            system_draft_creator,
        )
    if decision.protocol_id == ProtocolId.PROTO_EXPLORATION:
        return _exploration_result(
            session,
            character,
            llm_client,
            intent_context,
            debug_info,
            player_text,
            envelope,
            discovery_creator,
            thread_creator,
        )
    if decision.protocol_id == ProtocolId.PROTO_MEMORY_RECALL:
        return _memory_recall_result(
            session,
            character,
            player_text,
            llm_client,
            intent_context,
            debug_info,
            threads or [],
        )
    if decision.protocol_id == ProtocolId.PROTO_STAGNATION:
        return _stagnation_result(
            session,
            character,
            llm_client,
            intent_context,
            debug_info,
            player_text,
            envelope,
            threads or [],
            clocks or [],
            thread_creator,
        )
    if decision.freeze_time or not decision.execute:
        questions = decision.ooc_questions or [
            "Choose an action to proceed."
        ]
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason=decision.reason or "clarification",
            ),
            session,
            character,
            _ensure_resources(character.attributes_json),
            llm_client,
            intent_context,
            debug_info,
            clarification_questions=questions,
        )

    if envelope.gm_plan:
        project_result = _maybe_create_project(
            envelope,
            session,
            character,
            project_creator,
            llm_client,
            intent_context,
            debug_info,
        )
        if project_result is not None:
            return project_result

    intent, debug_info = _extract_intent_or_fallback(
        llm_client,
        player_text,
        intent_context,
    )
    return _execute_intent_pipeline(
        session,
        character,
        intent,
        llm_client,
        intent_context,
        debug_info,
        player_text,
    )


def _extract_intent_or_fallback(
    llm_client: OllamaClient,
    player_text: str,
    context: dict,
) -> tuple[Intent, dict]:
    try:
        if hasattr(llm_client, "extract_intent_with_debug"):
            return llm_client.extract_intent_with_debug(player_text, context)
        intent = llm_client.extract_intent(player_text, context)
        return (
            intent,
            {
                "raw_llm_output": None,
                "parsed_intent": intent.model_dump(),
                "validation_errors": [],
            },
        )
    except Exception as exc:
        return (
            Intent(
                action_type="ask_clarifying_question",
                dialogue="Could you clarify your intended action?",
                targets=[],
                movement=None,
            ),
            {
                "raw_llm_output": None,
                "parsed_intent": None,
                "validation_errors": [str(exc)],
            },
        )


def _validate_intent(
    intent: Intent,
    era_name: str,
    resources: dict,
    available_actions: Iterable[str],
) -> None:
    if intent.action_type in {"explore", "scene_request"}:
        return
    if available_actions and intent.action_type not in available_actions:
        raise TurnError("Action not allowed right now.")
    actions_required = _intent_to_turn_intent(intent).actions_required
    if actions_required < 0:
        raise TurnError("Invalid action cost.")
    if resources.get("actions", 0) < actions_required:
        raise TurnError("Not enough actions.")
    if intent.action_type == "use_power" and era_name.strip().lower() != "space":
        raise TurnError("Powers are locked outside the Space era.")


def _validate_impossible_action(
    intent: Intent,
    era_name: str,
    player_text: str | None,
) -> str | None:
    era_label = era_name.strip() or "this era"
    text_parts = [
        player_text or "",
        intent.dialogue or "",
        intent.item_used or "",
    ]
    combined = " ".join(text_parts).lower()
    spaceship_keywords = ("spaceship", "space ship", "starship", "star ship")
    if era_name.strip().lower() != "space" and any(
        keyword in combined for keyword in spaceship_keywords
    ):
        return (
            f"That action isn't possible. You are in a {era_label} setting. "
            "You do not possess a spaceship."
        )
    return None


def _execute_intent_pipeline(
    session: Any,
    character: Any,
    intent: Intent,
    llm_client: OllamaClient,
    intent_context: dict,
    debug_info: dict,
    player_text: str | None = None,
) -> TurnResult:
    if _should_log_retcon(intent, session):
        _log_retcon_event(session, intent)
    era_name = _extract_era_name(session)
    impossible_reason = _validate_impossible_action(intent, era_name, player_text)
    if impossible_reason:
        debug_info["validation_errors"].append(impossible_reason)
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason=impossible_reason,
            ),
            session,
            character,
            _ensure_resources(character.attributes_json),
            llm_client,
            intent_context,
            debug_info,
            clarification_questions=[
                "Flee the area on foot.",
                "Use known equipment.",
                "Attempt something unconventional within the scene.",
            ],
        )
    resources = _ensure_resources(character.attributes_json)
    if intent.action_type in {"ask_clarifying_question", "invalid"}:
        return _clarify_turn_result(
            intent,
            session,
            character,
            resources,
            llm_client,
            intent_context,
            debug_info,
            clarification_questions=None,
        )

    allowed_actions = intent_context.get("available_actions", [])
    try:
        _validate_intent(intent, era_name, resources, allowed_actions)
    except TurnError as exc:
        debug_info["validation_errors"].append(str(exc))
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason=str(exc),
            ),
            session,
            character,
            resources,
            llm_client,
            intent_context,
            debug_info,
            clarification_questions=None,
        )

    roll_index = _extract_roll_index(session)
    session_state = SessionState(seed=session.rng_seed or 0)
    _consume_rolls(session_state, roll_index)

    mechanics_intent = _intent_to_turn_intent(intent)
    outcome = _execute_mechanics(session_state, mechanics_intent)

    resources["actions"] -= mechanics_intent.actions_required
    updated_attributes = dict(character.attributes_json or {})
    updated_attributes["resources"] = resources
    updated_attributes["last_roll"] = outcome.get("attack_roll")
    updated_attributes["last_damage"] = outcome.get("damage")
    character.attributes_json = updated_attributes

    rolls = list(session_state.turn_log)
    roll_index += _count_rolls(session_state)
    _append_turn_log(session, intent, rolls, outcome, roll_index)

    state_diff = {
        "character": _build_character_state_diff(
            character,
            resources,
            outcome,
        ),
        "session": {"roll_index": roll_index},
    }

    narration = llm_client.generate_narration(
        _build_narration_request(session, character, intent, outcome)
    )
    outcome["narration"] = narration

    if _is_dead(state_diff["character"]):
        outcome["death"] = True
        outcome["death_journal"] = llm_client.generate_narration(
            _build_death_request(session, character, intent, outcome)
        )
    else:
        outcome["death"] = False
    narration_context = {
        "era": era_name,
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": outcome,
    }

    suggested_actions = _build_suggested_actions(
        intent_context.get("available_actions", [])
    )
    return TurnResult(
        intent=intent.model_dump(),
        rolls=rolls,
        outcome=outcome,
        state_diff=state_diff,
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=suggested_actions,
        needs_clarification=False,
        clarification_question=None,
        clarification_questions=[],
        project_created=None,
        raw_llm_output=debug_info["raw_llm_output"],
        parsed_intent=debug_info["parsed_intent"],
        validation_errors=debug_info["validation_errors"],
    )


def _execute_mechanics(session_state: SessionState, intent: TurnIntent) -> dict:
    if intent.action == "attack":
        attack_roll = roll_d20(session_state)
        attack_total = attack_roll + intent.skill_bonus + intent.attr_bonus
        hit = attack_total >= intent.target_ar
        damage = roll(session_state, intent.weapon_damage) if hit else 0
        return {
            "hit": hit,
            "attack_roll": attack_roll,
            "attack_total": attack_total,
            "target_ar": intent.target_ar,
            "damage": damage,
            "target": intent.target_label,
        }
    if intent.action == "explore":
        return {"explore": True}
    if intent.action == "scene_request":
        return {"scene_request": True}
    if intent.action == "interact":
        return {"interact": True, "target": intent.target_label}
    if intent.action == "use_power":
        return {"used_power": intent.power_id}
    if intent.action == "buy_item":
        return {"buy_item": True, "item": intent.item_used}
    if intent.action == "ask_gm":
        return {"ask_gm": True}
    if intent.action == "move":
        return {"moved": True, "movement": intent.movement}
    if intent.action == "pass":
        return {"pass": True}
    raise TurnError("Unsupported action.")


def _ensure_resources(attributes: dict | None) -> dict:
    resources = dict((attributes or {}).get("resources") or {})
    defaults = base_actions()
    resources.setdefault("actions", defaults["actions"])
    resources.setdefault("reactions", defaults["reactions"])
    return resources


def _extract_roll_index(session: Any) -> int:
    metadata = session.metadata_json
    if isinstance(metadata, dict):
        return int(metadata.get("roll_index", 0))
    return 0


def _append_turn_log(
    session: Any,
    intent: Intent,
    rolls: list[dict],
    outcome: dict,
    roll_index: int,
) -> None:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    log = metadata.get("turn_log")
    if not isinstance(log, list):
        log = []
    log.append(_compact_turn_log_entry(intent, rolls, outcome))
    metadata["turn_log"] = log
    metadata["roll_index"] = roll_index
    metadata["turn_index"] = len(log)
    session.metadata_json = metadata


def _consume_rolls(session_state: SessionState, roll_index: int) -> None:
    for _ in range(roll_index):
        session_state.rng.random()


def _count_rolls(session_state: SessionState) -> int:
    draws = 0
    for entry in session_state.turn_log:
        rolls = entry.get("rolls", [])
        if isinstance(rolls, list):
            draws += len(rolls)
    return draws


def _extract_era_name(session: Any) -> str:
    metadata = session.metadata_json
    if isinstance(metadata, dict):
        return str(metadata.get("era", ""))
    return ""


def _extract_location(session: Any) -> str:
    metadata = session.metadata_json
    if isinstance(metadata, dict):
        return str(metadata.get("location", ""))
    return ""


def _ensure_scene_state(session: Any) -> dict:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    scene = metadata.get("current_scene")
    if isinstance(scene, dict):
        summary = scene.get("summary")
        if scene.get("established") is True and isinstance(summary, str) and summary.strip():
            return scene
    summary = ""
    for key in ("scene_text", "scene"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            summary = value.strip()
            break
    location = _extract_location(session) or "unknown location"
    slug = _slugify(location)
    scene_state = {
        "scene_id": f"{slug}_entrance",
        "location_id": slug,
        "summary": summary or f"You are at the entrance of {location}.",
        "active_threats": [],
        "npcs_present": [],
        "open_hooks": ["Why this place matters", "Who sent you"],
        "established": True,
    }
    metadata["current_scene"] = scene_state
    session.metadata_json = metadata
    return scene_state


def _extract_scene_text(session: Any) -> str:
    metadata = session.metadata_json
    if isinstance(metadata, dict):
        for key in ("scene_text", "scene"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        scene = metadata.get("current_scene")
        if isinstance(scene, dict):
            summary = scene.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()
    return ""


def _has_scene_text(session: Any) -> bool:
    metadata = session.metadata_json
    if isinstance(metadata, dict):
        return bool(metadata.get("scene_text") or metadata.get("scene"))
    return False


def _store_scene_text(session: Any, text: str) -> None:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    metadata["scene_text"] = text
    scene = metadata.get("current_scene")
    if isinstance(scene, dict):
        scene.setdefault("summary", text)
        scene.setdefault("established", True)
        metadata["current_scene"] = scene
    session.metadata_json = metadata


def _shorten_text(text: str, limit: int = 220) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def _fallback_scene_text(session: Any) -> str:
    era = _extract_era_name(session) or "Unknown Era"
    location = _extract_location(session) or "an unfamiliar location"
    return (
        f"{era} - {location}. Dim light flickers across steel and shadow, "
        "and the low hum of distant machinery fills the air."
    )


def _extract_scene_lock(session: Any) -> dict:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    scene = metadata.get("current_scene")
    if isinstance(scene, dict):
        return {
            "established": bool(scene.get("established")),
            "summary": scene.get("summary"),
            "open_hooks": scene.get("open_hooks", []),
        }
    return {"established": False, "summary": None, "open_hooks": []}


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "scene"


def _ensure_scene_text(session: Any, character: Any, llm_client: OllamaClient) -> str:
    existing = _extract_scene_text(session)
    if existing:
        metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
        if "scene_text" not in metadata:
            metadata["scene_text"] = existing
            session.metadata_json = metadata
        return existing
    scene = _ensure_scene_state(session)
    summary = scene.get("summary")
    if isinstance(summary, str) and summary.strip():
        text = summary.strip()
        _store_scene_text(session, text)
        return text
    narration = llm_client.generate_narration(
        _build_scene_request(session, character)
    ).strip()
    if not narration:
        narration = _fallback_scene_text(session)
    _store_scene_text(session, narration)
    return narration


def _build_scene_request(session: Any, character: Any) -> NarrationRequest:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    setting = metadata.get("setting") if isinstance(metadata.get("setting"), dict) else {}
    return NarrationRequest(
        state_summary={
            "era": _extract_era_name(session),
            "location": _extract_location(session),
            "setting": setting,
            "character_id": getattr(character, "id", None),
            "scene_lock": _extract_scene_lock(session),
        },
        outcome={"establish_scene": True},
        tone="grounded",
    )


def _resolve_target_label(intent: Intent) -> str | None:
    if intent.targets:
        target = intent.targets[0]
        if target.name:
            return target.name
        if target.type:
            return target.type
        if target.id is not None:
            return f"target:{target.id}"
    return None


def _build_session_state(session: Any) -> dict:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    settings = metadata.get("settings")
    return {"settings": settings if isinstance(settings, dict) else {}}


def _build_envelope_context(session: Any, payload: dict | None) -> dict:
    scene_lock = _extract_scene_lock(session)
    payload_data = payload if isinstance(payload, dict) else {}
    suggested_action = payload_data.get("suggested_action")
    return {
        "era": _extract_era_name(session),
        "scene_summary": _shorten_text(scene_lock.get("summary") or _extract_scene_text(session)),
        "scene_lock": scene_lock,
        "dev_mode_enabled": _build_session_state(session)
        .get("settings", {})
        .get("dev_mode_enabled", False),
        "suggested_action": suggested_action,
    }


_MEMORY_RECALL_CONFIG: dict | None = None


def _load_memory_recall_config() -> dict:
    global _MEMORY_RECALL_CONFIG
    if _MEMORY_RECALL_CONFIG is not None:
        return _MEMORY_RECALL_CONFIG
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "docs" / "jsons" / "memory_recall.json"
    if not config_path.exists():
        _MEMORY_RECALL_CONFIG = {}
        return _MEMORY_RECALL_CONFIG
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    _MEMORY_RECALL_CONFIG = payload if isinstance(payload, dict) else {}
    return _MEMORY_RECALL_CONFIG


def _record_memory_recall_note(
    session: Any,
    *,
    player_text: str,
    recall_summary: dict,
    verification_questions: list[str],
    note_title: str | None,
    note_prefix: str | None,
) -> None:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    notes = metadata.get("gm_memory_notes")
    if not isinstance(notes, list):
        notes = []
    note_entry = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": note_title,
        "note_prefix": note_prefix,
        "player_text": player_text,
        "recall_summary": recall_summary,
        "verification_questions": verification_questions,
        "verified": False,
    }
    notes.append(note_entry)
    metadata["gm_memory_notes"] = notes
    session.metadata_json = metadata


def _intent_to_turn_intent(intent: Intent) -> TurnIntent:
    target_label = _resolve_target_label(intent)
    if intent.action_type == "explore":
        return TurnIntent(action="explore", actions_required=0)
    if intent.action_type == "scene_request":
        return TurnIntent(action="scene_request", actions_required=0)
    if intent.action_type == "interact":
        return TurnIntent(action="interact", actions_required=1, target_label=target_label)
    if intent.action_type == "ask_gm":
        return TurnIntent(action="ask_gm", actions_required=0)
    if intent.action_type == "use_power":
        return TurnIntent(
            action="use_power",
            power_id=intent.power_used,
            actions_required=1,
        )
    if intent.action_type == "attack":
        return TurnIntent(
            action="attack",
            target_ar=12,
            weapon_damage="1d6",
            actions_required=1,
            target_label=target_label or "nearest_threat",
        )
    if intent.action_type == "move":
        movement = intent.movement.model_dump() if intent.movement else None
        return TurnIntent(action="move", actions_required=1, movement=movement)
    if intent.action_type == "buy_item":
        return TurnIntent(
            action="buy_item",
            item_used=intent.item_used,
            actions_required=1,
        )
    return TurnIntent(action="pass", actions_required=0)


def _build_intent_context(session: Any, character: Any) -> dict:
    return {
        "era": _extract_era_name(session),
        "available_actions": [
            "explore",
            "scene_request",
            "interact",
            "move",
            "attack",
            "use_power",
            "buy_item",
            "ask_gm",
        ],
        "available_powers": _extract_available_powers(character),
        "notes": None,
    }


def _extract_available_powers(character: Any) -> list[str]:
    data = character.attributes_json or {}
    for key in ("powers", "powers_unlocked", "unlocked_powers"):
        value = data.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, dict):
            return [str(name) for name, enabled in value.items() if enabled]
        if isinstance(value, str):
            return [value]
    return []


def _build_narration_request(
    session: Any,
    character: Any,
    intent: Intent,
    outcome: dict,
) -> NarrationRequest:
    return NarrationRequest(
        state_summary={
            "era": _extract_era_name(session),
            "location": _extract_location(session),
            "current_scene": _extract_scene_lock(session),
            "character_id": getattr(character, "id", None),
            "resources": (character.attributes_json or {}).get("resources", {}),
        },
        outcome=outcome,
        tone="grounded",
    )


def _build_death_request(
    session: Any,
    character: Any,
    intent: Intent,
    outcome: dict,
) -> NarrationRequest:
    return NarrationRequest(
        state_summary={
            "era": _extract_era_name(session),
            "location": _extract_location(session),
            "character_id": getattr(character, "id", None),
            "event": "death",
        },
        outcome=outcome,
        tone="elegiac",
    )


def _compact_turn_log_entry(
    intent: Intent,
    rolls: list[dict],
    outcome: dict,
) -> dict:
    compact_rolls = [
        {"f": entry.get("formula"), "r": entry.get("result")} for entry in rolls
    ]
    return {
        "action": intent.action_type,
        "power": intent.power_used,
        "item": intent.item_used,
        "rolls": compact_rolls,
        "outcome": {"hit": outcome.get("hit"), "damage": outcome.get("damage")},
    }


def _clarify_turn_result(
    intent: Intent,
    session: Any,
    character: Any,
    resources: dict,
    llm_client: OllamaClient,
    intent_context: dict,
    debug_info: dict,
    clarification_questions: list[str] | None,
) -> TurnResult:
    questions = list(clarification_questions or [])
    question = intent.reason or intent.dialogue or "Please clarify your intended action."
    if not questions:
        questions = [question]
    elif not question and questions:
        question = questions[0]
    scene_text = _ensure_scene_text(session, character, llm_client)
    suggested_actions = _build_suggested_actions(
        intent_context.get("available_actions", [])
    )
    narration = _build_scene_update(scene_text, suggested_actions)
    outcome = {"clarify": True, "message": question, "narration": narration}
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": outcome,
    }
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome=outcome,
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=suggested_actions,
        needs_clarification=True,
        clarification_question=question,
        clarification_questions=questions,
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _is_dead(state: dict) -> bool:
    hp = state.get("hp")
    if hp is None:
        return False
    try:
        return int(hp) <= 0
    except (TypeError, ValueError):
        return False


def _build_character_state_diff(
    character: Any,
    resources: dict,
    outcome: dict,
) -> dict:
    attributes = character.attributes_json or {}
    derived = attributes.get("derived") if isinstance(attributes, dict) else {}
    derived = derived if isinstance(derived, dict) else {}
    hp = derived.get("hp")
    ap = derived.get("ap")
    return {
        "id": getattr(character, "id", None),
        "resources": resources,
        "hp": hp,
        "ap": ap,
        "statuses": getattr(character, "statuses_json", {}) or {},
        "last_roll": outcome.get("attack_roll"),
        "last_damage": outcome.get("damage"),
    }


def _build_scene_update(scene_text: str, suggested_actions: list[dict] | None = None) -> str:
    short_scene = _shorten_text(scene_text, limit=180)
    if not short_scene.endswith((".", "!", "?")):
        short_scene += "."
    prompt = "Choose a next action from the options below."
    return "\n".join(
        [short_scene, "No immediate changes are evident.", prompt]
        + _format_suggested_actions(suggested_actions)
    )


def _build_suggested_actions(available_actions: Iterable[str]) -> list[dict]:
    action_set = {str(action) for action in available_actions or []}
    candidates = [
        {
            "label": "Explore the area",
            "action_type": "explore",
            "payload": {},
        },
        {
            "label": "Interact with the nearest terminal",
            "action_type": "interact",
            "payload": {"targets": [{"name": "nearest terminal", "type": "object"}]},
        },
        {
            "label": "Move to cover",
            "action_type": "move",
            "payload": {"movement": {"mode": "walk", "distance": 5, "destination": "cover"}},
        },
        {
            "label": "Attack the nearest threat",
            "action_type": "attack",
            "payload": {"targets": []},
        },
        {
            "label": "Request a closer look at the scene",
            "action_type": "scene_request",
            "payload": {},
        },
        {
            "label": "Ask the GM for guidance",
            "action_type": "ask_gm",
            "payload": {"dialogue": "What stands out right now?"},
        },
    ]
    filtered = [item for item in candidates if item["action_type"] in action_set]
    if len(filtered) < 3:
        fallback = {"label": "Explore the area", "action_type": "explore", "payload": {}}
        while len(filtered) < 3:
            filtered.append(fallback)
    return filtered[:5]


def _format_suggested_actions(suggested_actions: list[dict] | None) -> list[str]:
    if not suggested_actions:
        return []
    lines = ["Available actions:"]
    for action in suggested_actions:
        label = action.get("label") or action.get("action_type") or "Action"
        lines.append(f"- {label}")
    return lines


def _is_memory_recall_request(player_text: str) -> bool:
    text = player_text.strip().lower()
    if not text:
        return False
    triggers = (
        "what do i know",
        "what do we know",
        "what do i remember",
        "why am i here",
        "didn't you say",
        "did you say",
        "what did you say",
        "what do you remember",
    )
    return any(trigger in text for trigger in triggers)


def _memory_recall_result(
    session: Any,
    character: Any,
    player_text: str,
    llm_client: OllamaClient,
    intent_context: dict,
    debug_info: dict,
    threads: list[Any],
) -> TurnResult:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    setup = metadata.get("session_setup") if isinstance(metadata.get("session_setup"), dict) else {}
    starting = setup.get("starting_situation") if isinstance(setup.get("starting_situation"), dict) else {}
    goal = starting.get("hook") or "Unknown"
    npcs = starting.get("npcs") if isinstance(starting.get("npcs"), list) else []
    sender = npcs[0] if npcs else "Unknown"
    facts = _recent_fact_lines(metadata, limit=4)
    rumors = _collect_rumors(threads, limit=3)
    scene = _extract_scene_lock(session)
    scene_status = scene.get("summary") or "No scene established yet."
    recall_summary = {
        "goal": goal,
        "sender": sender,
        "facts": facts,
        "rumors": rumors,
        "scene": scene,
    }
    recall_config = _load_memory_recall_config()
    verification_questions = recall_config.get("verification_questions")
    if not isinstance(verification_questions, list):
        verification_questions = []
    note_title = recall_config.get("note_title")
    note_prefix = recall_config.get("note_prefix")
    _record_memory_recall_note(
        session,
        player_text=player_text,
        recall_summary=recall_summary,
        verification_questions=verification_questions,
        note_title=note_title if isinstance(note_title, str) else None,
        note_prefix=note_prefix if isinstance(note_prefix, str) else None,
    )

    lines = [
        "Out of character: Here's what you currently know:",
        f"- Last known goal: {goal}",
        f"- Who sent you: {sender}",
        f"- Current location: {scene_status}",
    ]
    if facts:
        lines.append("- Confirmed facts:")
        lines.extend([f"  - {fact}" for fact in facts])
    if rumors:
        lines.append("- Rumors:")
        lines.extend([f"  - {rumor}" for rumor in rumors])

    options = [
        "Search your memory for more clues (risk: false recollection).",
        "Investigate the scene for new evidence.",
        "Leave the area.",
    ]
    lines.append("If you want, you can:")
    lines.extend([f"- {option}" for option in options])

    suggested_actions = [
        {
            "label": "Search memory for more clues",
            "action_type": "explore",
            "payload": {"metadata": {"memory_search": True}},
        },
        {
            "label": "Investigate the scene",
            "action_type": "interact",
            "payload": {"targets": [{"name": "scene", "type": "location"}]},
        },
        {
            "label": "Leave the area",
            "action_type": "move",
            "payload": {"movement": {"mode": "walk", "distance": 10, "destination": "exit"}},
        },
    ]

    intent = Intent(action_type="ask_gm", targets=[], dialogue="Memory recall.")
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": {"memory_recall": True},
    }
    narration_request = NarrationRequest(
        state_summary={
            "era": _extract_era_name(session),
            "location": _extract_location(session),
            "memory_recall": recall_summary,
        },
        outcome={
            "memory_recall": True,
            "verification_questions": verification_questions,
        },
        tone="reflective",
    )
    narration = llm_client.generate_narration(narration_request).strip()
    if not narration:
        narration = "\n".join(lines)
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome={
            "memory_recall": True,
            "facts": facts,
            "rumors": rumors,
            "summary": lines,
            "gm_notes": {
                "title": note_title,
                "note_prefix": note_prefix,
                "verification_questions": verification_questions,
            },
        },
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=suggested_actions,
        needs_clarification=False,
        clarification_question=None,
        clarification_questions=[],
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _recent_fact_lines(metadata: dict, limit: int = 4) -> list[str]:
    log = metadata.get("turn_log")
    if not isinstance(log, list) or not log:
        return []
    recent = log[-limit:]
    facts = []
    for entry in recent:
        line = _format_turn_entry(entry)
        if line:
            facts.append(line)
    return facts


def _collect_rumors(threads: list[Any], limit: int = 3) -> list[str]:
    rumors = []
    for thread in threads:
        if getattr(thread, "type", "") != "rumor":
            continue
        text = getattr(thread, "text", "")
        if text:
            rumors.append(text)
        if len(rumors) >= limit:
            break
    return rumors


def _rule_edge_case_result(
    session: Any,
    character: Any,
    intent_context: dict,
    debug_info: dict,
    player_text: str,
    envelope: Any,
) -> TurnResult:
    question = _build_rule_question(player_text, envelope)
    affected_systems = _build_affected_systems(envelope)
    if _dev_mode_enabled(session):
        proposal = _build_rule_proposal(envelope, question)
        narration = (
            "OOC: Mechanics edge case detected.\n"
            f"Question: {question}\n"
            f"Proposed addition: {proposal}\n"
            "Please provide a ruling."
        )
        suggested_actions = [
            {
                "label": "Provide ruling",
                "action_type": "ask_gm",
                "payload": {
                    "dialogue": "Ruling: [describe the rule to apply].",
                    "metadata": {"resolution": "ruling"},
                },
            },
            {
                "label": "Log rule addition",
                "action_type": "ask_gm",
                "payload": {
                    "dialogue": "Add rule: [schema/rule addition].",
                    "metadata": {"resolution": "rule_addition"},
                },
            },
        ]
        intent = Intent(
            action_type="ask_clarifying_question",
            targets=[],
            dialogue="Please provide a ruling for this edge case.",
        )
        narration_context = {
            "era": _extract_era_name(session),
            "location": _extract_location(session),
            "intent": intent.model_dump(),
            "outcome": {"rule_edge_case": True},
        }
        return TurnResult(
            intent=intent.model_dump(),
            rolls=[],
            outcome={"rule_edge_case": True, "proposal": proposal},
            state_diff={},
            narration_prompt_context=narration_context,
            narration=narration,
            suggested_actions=suggested_actions,
            needs_clarification=True,
            clarification_question="Please provide a ruling for this edge case.",
            clarification_questions=[
                "Provide a ruling.",
                "Add a schema/rule addition.",
            ],
            project_created=None,
            raw_llm_output=debug_info.get("raw_llm_output"),
            parsed_intent=debug_info.get("parsed_intent"),
            validation_errors=debug_info.get("validation_errors", []),
        )

    ruling = "Conservative ruling: no mechanical effect until clarified."
    ruling_note = {
        "question": question,
        "ruling": ruling,
        "affected_systems": affected_systems,
    }
    narration = (
        "OOC: Mechanics edge case detected.\n"
        f"{ruling}"
    )
    intent = Intent(
        action_type="ask_gm",
        targets=[],
        dialogue="Proceed under conservative ruling.",
    )
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": {"rule_edge_case": True},
    }
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome={"rule_edge_case": True, "ruling_note": ruling_note},
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=_build_suggested_actions(
            intent_context.get("available_actions", [])
        ),
        needs_clarification=False,
        clarification_question=None,
        clarification_questions=[],
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _build_rule_question(player_text: str, envelope: Any) -> str:
    summary = player_text.strip() if player_text else "Unspecified request"
    classification = getattr(envelope, "classification", None)
    category = None
    if classification:
        category = getattr(classification, "primary_category", None)
    if category:
        return f"{summary} (category: {category})"
    return summary


def _build_affected_systems(envelope: Any) -> list[str]:
    classification = getattr(envelope, "classification", None)
    systems = []
    if classification:
        primary = getattr(classification, "primary_category", None)
        secondary = getattr(classification, "secondary_category", None)
        if primary:
            systems.append(str(primary))
        if secondary:
            systems.append(str(secondary))
    return systems or ["mechanics"]


def _build_rule_proposal(envelope: Any, question: str) -> str:
    category = None
    classification = getattr(envelope, "classification", None)
    if classification:
        category = getattr(classification, "primary_category", None)
    category_label = category or "mechanics"
    return f"Add a rule entry for {category_label} edge cases: {question}"


def _content_gap_result(
    session: Any,
    character: Any,
    intent_context: dict,
    debug_info: dict,
    player_text: str,
    envelope: Any,
    system_draft_creator: Callable[[dict], dict] | None,
) -> TurnResult:
    if not _dev_mode_enabled(session):
        intent = Intent(
            action_type="ask_clarifying_question",
            targets=[],
            dialogue="This system is missing. Do you want to proceed without it?",
        )
        narration_context = {
            "era": _extract_era_name(session),
            "location": _extract_location(session),
            "intent": intent.model_dump(),
            "outcome": {"content_gap": True},
        }
        return TurnResult(
            intent=intent.model_dump(),
            rolls=[],
            outcome={"content_gap": True},
            state_diff={},
            narration_prompt_context=narration_context,
            narration="OOC: Missing system content. Proceed with a conservative fallback.",
            suggested_actions=_build_suggested_actions(
                intent_context.get("available_actions", [])
            ),
            needs_clarification=True,
            clarification_question="This system is missing. Do you want to proceed without it?",
            clarification_questions=[
                "Proceed with conservative fallback.",
                "Pause and define the missing system.",
            ],
            project_created=None,
            raw_llm_output=debug_info.get("raw_llm_output"),
            parsed_intent=debug_info.get("parsed_intent"),
            validation_errors=debug_info.get("validation_errors", []),
        )

    if system_draft_creator is None:
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason="System draft creation unavailable.",
            ),
            session,
            character,
            _ensure_resources(character.attributes_json),
            OllamaClient(),
            intent_context,
            debug_info,
            clarification_questions=["System draft creation is unavailable."],
        )

    draft_payload = _build_system_draft_payload(player_text, envelope)
    try:
        draft = SystemDraftSchema.model_validate(draft_payload)
    except ValueError as exc:
        debug_info["validation_errors"].append(str(exc))
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason="System draft validation failed.",
            ),
            session,
            character,
            _ensure_resources(character.attributes_json),
            OllamaClient(),
            intent_context,
            debug_info,
            clarification_questions=["System draft validation failed."],
        )

    created = system_draft_creator(
        {
            "session_id": getattr(session, "id", None),
            **draft.model_dump(),
        }
    )
    narration = (
        "OOC: Missing system content. Draft proposed and stored for review."
    )
    intent = Intent(
        action_type="ask_clarifying_question",
        targets=[],
        dialogue="Do you want to activate this system draft?",
    )
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": {"content_gap": True, "system_draft_created": True},
    }
    suggested_actions = [
        {
            "label": "Accept draft",
            "action_type": "ask_gm",
            "payload": {"metadata": {"resolution": "accept_system_draft"}},
        },
        {
            "label": "Revise draft",
            "action_type": "ask_gm",
            "payload": {"metadata": {"resolution": "revise_system_draft"}},
        },
    ]
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome={"content_gap": True, "system_draft": created},
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=suggested_actions,
        needs_clarification=True,
        clarification_question="Do you want to activate this system draft?",
        clarification_questions=["Accept the draft.", "Revise the draft."],
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _build_system_draft_payload(player_text: str, envelope: Any) -> dict:
    name = _infer_system_name(player_text, envelope)
    if name.lower() == "alchemy":
        return {
            "name": "Alchemy",
            "inputs": [
                {
                    "mechanic": "project",
                    "description": "Gather alchemical reagents",
                    "payload": {
                        "type": "craft",
                        "requirements": {"materials": ["reagents"]},
                        "work_units_total": 2,
                    },
                }
            ],
            "process": [
                {
                    "mechanic": "roll",
                    "description": "Perform an alchemy check",
                    "payload": {"skill": "Alchemy", "dice": "1d20"},
                }
            ],
            "outputs": [
                {
                    "mechanic": "project",
                    "description": "Recipe: Minor Tonic",
                    "payload": {
                        "name": "Minor Tonic",
                        "type": "craft",
                        "requirements": {"materials": ["reagents", "solvent"]},
                        "work_units_total": 3,
                    },
                },
                {
                    "mechanic": "project",
                    "description": "Recipe: Smoke Bomb",
                    "payload": {
                        "name": "Smoke Bomb",
                        "type": "craft",
                        "requirements": {"materials": ["reagents", "ash"]},
                        "work_units_total": 2,
                    },
                },
            ],
            "costs": [
                {
                    "mechanic": "status",
                    "description": "Minor burns if mishandled",
                    "payload": {"status": "Injured", "level": 1, "duration": 1},
                }
            ],
            "risks": [
                {
                    "mechanic": "status",
                    "description": "Toxic exposure on failure",
                    "payload": {"status": "Toxin", "level": 1, "duration": 2},
                }
            ],
            "checks": [
                {
                    "mechanic": "roll",
                    "description": "Stability check",
                    "payload": {"skill": "Alchemy", "dice": "1d20"},
                }
            ],
        }
    return {
        "name": name,
        "inputs": [],
        "process": [],
        "outputs": [],
        "costs": [],
        "risks": [],
        "checks": [],
    }


def _infer_system_name(player_text: str, envelope: Any) -> str:
    lowered = (player_text or "").strip().lower()
    if "alchemy" in lowered:
        return "Alchemy"
    classification = getattr(envelope, "classification", None)
    if classification:
        primary = getattr(classification, "primary_category", None)
        if isinstance(primary, str) and primary.strip():
            return primary.strip().title()
    return "New System"


def _exploration_result(
    session: Any,
    character: Any,
    llm_client: OllamaClient,
    intent_context: dict,
    debug_info: dict,
    player_text: str,
    envelope: Any,
    discovery_creator: Callable[[dict], dict] | None,
    thread_creator: Callable[[dict], dict] | None,
) -> TurnResult:
    tags = _extract_exploration_tags(session, player_text)
    gradient, index = _choose_truth_gradient(session, tags)
    summary = _build_discovery_summary(gradient, tags)
    discovery_payload = {
        "session_id": getattr(session, "id", None),
        "gradient": gradient,
        "summary": summary,
        "tags": tags,
        "context": {
            "player_text": player_text,
            "classification": getattr(envelope, "classification", None).model_dump()
            if getattr(envelope, "classification", None)
            else None,
        },
    }
    created_discovery = (
        discovery_creator(discovery_payload)
        if discovery_creator
        else discovery_payload
    )
    thread_payload = _build_thread_from_discovery(
        session,
        created_discovery,
        gradient,
    )
    created_thread = (
        thread_creator(thread_payload) if thread_creator else thread_payload
    )
    _bump_exploration_index(session, index)
    narration = llm_client.generate_narration(
        NarrationRequest(
            state_summary={
                "era": _extract_era_name(session),
                "location": _extract_location(session),
                "tags": tags,
                "discovery": created_discovery,
            },
            outcome={"discovery": created_discovery, "thread": created_thread},
            tone="grounded",
        )
    )
    intent = Intent(action_type="explore", targets=[])
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": {"discovery": created_discovery, "thread": created_thread},
    }
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome={
            "exploration": True,
            "discovery": created_discovery,
            "thread": created_thread,
            "narration": narration,
        },
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=_build_suggested_actions(
            intent_context.get("available_actions", [])
        ),
        needs_clarification=False,
        clarification_question=None,
        clarification_questions=[],
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _extract_exploration_tags(session: Any, player_text: str) -> list[str]:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    tags: list[str] = []
    for key in ("era", "location"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            tags.append(value.strip().lower())
    setting = metadata.get("setting") if isinstance(metadata.get("setting"), dict) else {}
    setting_type = setting.get("type")
    if isinstance(setting_type, str) and setting_type.strip():
        tags.append(setting_type.strip().lower())
    tone_tags = setting.get("tone_tags")
    if isinstance(tone_tags, list):
        tags.extend(
            [str(tag).strip().lower() for tag in tone_tags if str(tag).strip()]
        )
    if player_text:
        tags.extend(
            [part.strip().lower() for part in player_text.split() if part.strip()]
        )
    return sorted({tag for tag in tags if tag})


def _stable_hash_tags(tags: list[str]) -> int:
    joined = "|".join(tags).encode("utf-8")
    digest = hashlib.sha256(joined).hexdigest()
    return int(digest[:8], 16)


def _choose_truth_gradient(session: Any, tags: list[str]) -> tuple[str, int]:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    exploration_index = int(metadata.get("exploration_index", 0))
    seed = (session.rng_seed or 0) + _stable_hash_tags(tags) + exploration_index
    rng = random.Random(seed)
    gradients = ["myth", "partial", "lost", "false", "dangerous"]
    return gradients[rng.randrange(len(gradients))], exploration_index


def _bump_exploration_index(session: Any, current_index: int) -> None:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    metadata["exploration_index"] = current_index + 1
    session.metadata_json = metadata


def _build_discovery_summary(gradient: str, tags: list[str]) -> str:
    tag_hint = tags[0] if tags else "the area"
    summaries = {
        "myth": f"A legend surfaces about {tag_hint}, whispered but unproven.",
        "partial": f"You uncover partial clues tied to {tag_hint}.",
        "lost": f"The trail for {tag_hint} goes cold, hinting at a hidden path.",
        "false": f"A false lead about {tag_hint} points elsewhere.",
        "dangerous": f"A dangerous discovery in {tag_hint} hints at immediate threat.",
    }
    return summaries.get(gradient, "You uncover a lead worth following.")


def _build_thread_from_discovery(
    session: Any,
    discovery: dict,
    gradient: str,
) -> dict:
    thread_type_map = {
        "myth": "rumor",
        "partial": "hook",
        "lost": "foreshadow",
        "false": "rumor",
        "dangerous": "consequence",
    }
    urgency_map = {
        "myth": "low",
        "partial": "med",
        "lost": "low",
        "false": "low",
        "dangerous": "high",
    }
    summary = discovery.get("summary") or "A new lead emerges."
    text = f"{summary} Follow up to press the lead."
    return {
        "session_id": getattr(session, "id", None),
        "type": thread_type_map.get(gradient, "hook"),
        "status": "open",
        "urgency": urgency_map.get(gradient, "med"),
        "visibility": "player",
        "related_entities": {"discovery_id": discovery.get("id")},
        "text": text,
    }


def _stagnation_result(
    session: Any,
    character: Any,
    llm_client: OllamaClient,
    intent_context: dict,
    debug_info: dict,
    player_text: str,
    envelope: Any,
    threads: list[Any],
    clocks: list[Any],
    thread_creator: Callable[[dict], dict] | None,
) -> TurnResult:
    open_threads = [thread for thread in threads if getattr(thread, "status", "") == "open"]
    active_clocks = [
        clock for clock in clocks
        if getattr(clock, "steps_done", 0) < getattr(clock, "steps_total", 0)
    ]
    preference_profile = _load_preference_profile(session)
    action = _choose_stagnation_action(session, open_threads, active_clocks)
    outcome = {"stagnation": True, "action": action}

    if action == "escalate_clock" and active_clocks:
        clock = active_clocks[0]
        clock.steps_done = min(clock.steps_total, clock.steps_done + 1)
        outcome["clock_escalated"] = {
            "id": getattr(clock, "id", None),
            "name": getattr(clock, "name", None),
            "steps_done": clock.steps_done,
            "steps_total": clock.steps_total,
        }

    if action == "thread_consequence" and open_threads:
        base_thread = open_threads[0]
        outcome["thread_consequence"] = {
            "id": getattr(base_thread, "id", None),
            "text": getattr(base_thread, "text", None),
        }

    hook_payload = _build_stagnation_hook(
        session,
        action,
        preference_profile,
        outcome,
    )
    created_hook = thread_creator(hook_payload) if thread_creator else hook_payload
    outcome["hook"] = created_hook

    _update_pacing_tag(session, "tension")

    narration = llm_client.generate_narration(
        NarrationRequest(
            state_summary={
                "era": _extract_era_name(session),
                "location": _extract_location(session),
                "preference_profile": preference_profile,
                "stagnation_action": action,
            },
            outcome=outcome,
            tone="tense",
        )
    )
    intent = Intent(action_type="explore", targets=[])
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": outcome,
    }
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome=outcome,
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=_build_suggested_actions(
            intent_context.get("available_actions", [])
        ),
        needs_clarification=False,
        clarification_question=None,
        clarification_questions=[],
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _choose_stagnation_action(
    session: Any,
    open_threads: list[Any],
    active_clocks: list[Any],
) -> str:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    stagnation_index = int(metadata.get("stagnation_index", 0))
    options = ["opportunity"]
    if active_clocks:
        options.append("escalate_clock")
    if open_threads:
        options.append("thread_consequence")
    seed = (session.rng_seed or 0) + stagnation_index + len(options) * 13
    rng = random.Random(seed)
    choice = options[rng.randrange(len(options))]
    metadata["stagnation_index"] = stagnation_index + 1
    session.metadata_json = metadata
    return choice


def _load_preference_profile(session: Any) -> dict:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    prefs = metadata.get("player_prefs")
    if isinstance(prefs, dict):
        return prefs
    return {"interests": ["mystery", "action"]}


def _build_stagnation_hook(
    session: Any,
    action: str,
    preference_profile: dict,
    outcome: dict,
) -> dict:
    interests = preference_profile.get("interests")
    if not isinstance(interests, list):
        interests = ["mystery"]
    interest = str(interests[0]) if interests else "mystery"
    base = {
        "session_id": getattr(session, "id", None),
        "type": "hook",
        "status": "open",
        "urgency": "high",
        "visibility": "player",
        "related_entities": {"origin": "stagnation"},
    }
    if action == "escalate_clock":
        clock_name = outcome.get("clock_escalated", {}).get("name") or "a looming deadline"
        text = f"Tension rises: {clock_name} advances and forces a response."
    elif action == "thread_consequence":
        thread_text = outcome.get("thread_consequence", {}).get("text") or "an ignored lead"
        text = f"Tension rises: ignoring {thread_text} triggers a consequence."
    else:
        text = f"Tension rises: an opportunity in {interest} demands attention."
    base["text"] = text
    return base


def _update_pacing_tag(session: Any, tag: str) -> None:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    metadata["pacing_tag"] = tag
    session.metadata_json = metadata


def _retcon_dispute_result(
    session: Any,
    character: Any,
    intent_context: dict,
    debug_info: dict,
) -> TurnResult:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    citations = _build_turn_citations(metadata)
    rolling_summary = metadata.get("rolling_summary") or ""
    narration_parts = [
        "OOC: Retcon dispute.",
    ]
    if rolling_summary:
        narration_parts.append(f"Rolling summary: {rolling_summary}")
    if citations:
        narration_parts.append("Here is what was said/done:")
        narration_parts.extend(citations)
    else:
        narration_parts.append("No turn log is available yet.")
    narration_parts.append(
        "Choose a resolution: clarify misunderstanding or retcon with minimal disruption."
    )
    narration = "\n".join(narration_parts)
    suggested_actions = [
        {
            "label": "Clarify misunderstanding",
            "action_type": "ask_gm",
            "payload": {
                "dialogue": "Clarify the misunderstanding and restate the intent.",
                "metadata": {"resolution": "clarify"},
            },
        },
        {
            "label": "Retcon with minimal disruption",
            "action_type": "ask_gm",
            "payload": {
                "dialogue": "Apply a minimal retcon to resolve the dispute.",
                "metadata": {"resolution": "retcon"},
            },
        },
    ]
    intent = Intent(
        action_type="ask_clarifying_question",
        targets=[],
        dialogue="Which resolution should we apply?",
    )
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": {"retcon_dispute": True},
    }
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome={"retcon_dispute": True, "citations": citations},
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=suggested_actions,
        needs_clarification=True,
        clarification_question="Which resolution should we apply?",
        clarification_questions=[
            "Clarify misunderstanding",
            "Retcon with minimal disruption",
        ],
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _build_turn_citations(metadata: dict, limit: int = 5) -> list[str]:
    log = metadata.get("turn_log")
    if not isinstance(log, list) or not log:
        return []
    total_turns = metadata.get("turn_index")
    if not isinstance(total_turns, int):
        total_turns = len(log)
    offset = max(0, total_turns - len(log))
    start_index = max(0, len(log) - limit)
    citations = []
    for idx in range(start_index, len(log)):
        entry = log[idx]
        turn_number = offset + idx + 1
        line = _format_turn_entry(entry)
        if line:
            citations.append(f"Turn {turn_number}: {line}")
    return citations


def _format_turn_entry(entry: dict) -> str:
    if not isinstance(entry, dict):
        return ""
    parts: list[str] = []
    action = entry.get("action")
    if action:
        parts.append(f"action={action}")
    power = entry.get("power")
    if power:
        parts.append(f"power={power}")
    item = entry.get("item")
    if item:
        parts.append(f"item={item}")
    outcome = entry.get("outcome")
    if isinstance(outcome, dict):
        if "hit" in outcome:
            parts.append(f"hit={outcome.get('hit')}")
        if outcome.get("damage") is not None:
            parts.append(f"damage={outcome.get('damage')}")
    return " ".join(parts)


def _dev_mode_enabled(session: Any) -> bool:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    settings = metadata.get("settings")
    if isinstance(settings, dict):
        value = settings.get("dev_mode_enabled")
        if value is None:
            value = settings.get("dev_mode")
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
    return False


def _should_log_retcon(intent: Intent, session: Any) -> bool:
    if intent.action_type != "ask_gm":
        return False
    metadata = intent.metadata or {}
    return (
        metadata.get("resolution") == "retcon"
        and _dev_mode_enabled(session)
    )


def _log_retcon_event(session: Any, intent: Intent) -> None:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    retcon_log = metadata.get("retcon_log")
    if not isinstance(retcon_log, list):
        retcon_log = []
    retcon_log.append(
        {
            "turn_index": metadata.get("turn_index"),
            "note": intent.dialogue or intent.reason or "retcon requested",
        }
    )
    metadata["retcon_log"] = retcon_log
    session.metadata_json = metadata


def _maybe_store_ruling(db, outcome: dict) -> None:
    if not isinstance(outcome, dict):
        return
    note = outcome.get("ruling_note")
    if not isinstance(note, dict):
        return
    question = note.get("question")
    ruling = note.get("ruling")
    if not question or not ruling:
        return
    affected = note.get("affected_systems")
    systems = affected if isinstance(affected, list) else None
    db.add(
        Ruling(
            question=str(question),
            ruling=str(ruling),
            affected_systems_json=systems,
        )
    )


def _update_player_profile(db, session: Any, intent_payload: dict) -> None:
    action_type = None
    if isinstance(intent_payload, dict):
        action_type = intent_payload.get("action_type") or intent_payload.get("action")
    if not action_type:
        return
    if action_type in {"ask_clarifying_question", "invalid"}:
        return
    profile = _get_or_create_profile(db, session)
    if profile is None:
        return
    interests = profile.interests_json if isinstance(profile.interests_json, dict) else {}
    updated = _apply_interest_update(interests, action_type)
    profile.interests_json = updated


def _get_or_create_profile(db, session: Any) -> PlayerProfile | None:
    session_id = getattr(session, "id", None)
    if session_id is None:
        return None
    profile = (
        db.query(PlayerProfile)
        .filter(PlayerProfile.session_id == session_id)
        .first()
    )
    if profile is None:
        profile = PlayerProfile(
            session_id=session_id,
            tone_prefs_json={},
            themes_json={},
            pacing_json={},
            challenge_json={},
            boundaries_json={},
            interests_json=_default_interest_weights(),
        )
        db.add(profile)
    return profile


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


def _apply_interest_update(interests: dict, action_type: str) -> dict:
    mapping = {
        "attack": "combat",
        "use_power": "combat",
        "buy_item": "crafting",
        "project_create": "crafting",
        "explore": "exploration",
        "scene_request": "exploration",
        "move": "exploration",
        "interact": "politics",
        "ask_gm": "mystery",
    }
    category = mapping.get(action_type)
    if category is None:
        return interests
    entry = interests.get(category)
    if not isinstance(entry, dict):
        entry = {"count": 0, "weight": 0.0}
    count = entry.get("count", 0)
    weight = entry.get("weight", 0.0)
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    try:
        weight = float(weight)
    except (TypeError, ValueError):
        weight = 0.0
    count += 1
    weight += 1.0
    entry = {"count": count, "weight": weight}
    interests[category] = entry
    return interests


def _maybe_create_project(
    envelope,
    session: Any,
    character: Any,
    project_creator: Callable[[dict], dict] | None,
    llm_client: OllamaClient,
    intent_context: dict,
    debug_info: dict,
) -> TurnResult | None:
    if envelope.gm_plan is None:
        return None
    step = _find_project_step(envelope.gm_plan)
    if step is None:
        return None
    if project_creator is None:
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason="Project creation unavailable.",
            ),
            session,
            character,
            _ensure_resources(character.attributes_json),
            llm_client,
            intent_context,
            debug_info,
            clarification_questions=["Project tooling is not available yet."],
        )

    project_payload = _build_project_payload(step, session, character)
    try:
        project_data = project_creator(project_payload)
    except Exception as exc:
        debug_info["validation_errors"].append(str(exc))
        return _clarify_turn_result(
            Intent(
                action_type="ask_clarifying_question",
                targets=[],
                reason="Project creation failed.",
            ),
            session,
            character,
            _ensure_resources(character.attributes_json),
            llm_client,
            intent_context,
            debug_info,
            clarification_questions=["Project creation failed. Try again?"],
        )
    questions = _project_questions(step)
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "event": "project_created",
        "project": {"name": project_data.get("name"), "type": project_data.get("type")},
    }
    narration = llm_client.generate_narration(
        NarrationRequest(
            state_summary=narration_context,
            outcome={"project_created": project_data},
            tone="grounded",
        )
    )
    return TurnResult(
        intent={"action_type": "project_create"},
        rolls=[],
        outcome={"project_created": True, "narration": narration},
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=[],
        needs_clarification=bool(questions),
        clarification_question=questions[0] if questions else None,
        clarification_questions=questions,
        project_created=project_data,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )


def _find_project_step(plan) -> Any | None:
    for step in plan.root:
        if step.type in {"craft", "improvise"}:
            complexity = step.complexity or 0
            if complexity > 1 or step.time_cost in {"hours", "days"}:
                return step
    return None


def _build_project_payload(step, session: Any, character: Any) -> dict:
    base_name = step.targets[0] if step.targets else None
    label = base_name or step.notes or "Project"
    if step.type == "craft":
        project_type = "craft"
    else:
        project_type = "build"
    requirements = {"materials": [], "skills": []}
    if step.skill_used:
        requirements["skills"].append(step.skill_used)
    return {
        "session_id": getattr(session, "id", None),
        "character_id": getattr(character, "id", None),
        "name": label if label else "Project",
        "type": project_type,
        "requirements": requirements,
        "constraints": None,
        "work_units_total": max(2, step.complexity or 2),
        "work_units_done": 0,
        "status": "active",
    }


def _project_questions(step) -> list[str]:
    questions: list[str] = []
    notes = (step.notes or "").lower()
    if "material" not in notes:
        questions.append("What materials or parts are available?")
    if step.skill_used is None and "method" not in notes:
        questions.append("What method or approach should drive the build?")
    if not step.targets:
        questions.append("What is the specific build target?")
    return questions[:3]


def _scene_intro_result(
    session: Any,
    character: Any,
    llm_client: OllamaClient,
    intent_context: dict,
    debug_info: dict,
) -> TurnResult:
    scene_text = _ensure_scene_text(session, character, llm_client)
    suggested_actions = _build_suggested_actions(
        intent_context.get("available_actions", [])
    )
    intent = Intent(
        action_type="ask_clarifying_question",
        targets=[],
        dialogue="Choose an action to proceed.",
        movement=None,
    )
    narration_context = {
        "era": _extract_era_name(session),
        "location": _extract_location(session),
        "intent": intent.model_dump(),
        "outcome": {"scene_established": True},
    }
    narration = "\n".join(
        [scene_text, "Choose a next action from the options below."]
        + _format_suggested_actions(suggested_actions)
    )
    return TurnResult(
        intent=intent.model_dump(),
        rolls=[],
        outcome={"scene_established": True, "narration": narration},
        state_diff={},
        narration_prompt_context=narration_context,
        narration=narration,
        suggested_actions=suggested_actions,
        needs_clarification=True,
        clarification_question="Choose an action to proceed.",
        clarification_questions=["Choose an action to proceed."],
        project_created=None,
        raw_llm_output=debug_info.get("raw_llm_output"),
        parsed_intent=debug_info.get("parsed_intent"),
        validation_errors=debug_info.get("validation_errors", []),
    )
