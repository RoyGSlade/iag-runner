from __future__ import annotations

from typing import Iterable

from db import SessionLocal
from models import MemoryCard, Project, Session as SessionModel

RECENT_TURN_LIMIT = 30
ROLLING_SUMMARY_LIMIT = 800
SUMMARY_SEPARATOR = " | "


def promote_memories(session_id: int, turn_count_threshold: int = 100) -> bool:
    with SessionLocal() as db:
        session = db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found.")
        updated = promote_memories_for_session(db, session, turn_count_threshold)
        if updated:
            db.commit()
            db.refresh(session)
        return updated


def promote_memories_for_session(db, session, turn_count_threshold: int) -> bool:
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    log = metadata.get("turn_log")
    if not isinstance(log, list) or not log:
        return False

    updated = False
    recent_entries = log[-RECENT_TURN_LIMIT:] if len(log) > RECENT_TURN_LIMIT else list(log)
    recent_summary = _facts_from_entries(recent_entries)
    if metadata.get("recent_summary") != recent_summary:
        metadata["recent_summary"] = recent_summary
        updated = True

    if len(log) >= turn_count_threshold:
        old_entries = log[:-RECENT_TURN_LIMIT] if len(log) > RECENT_TURN_LIMIT else []
        old_facts = _facts_from_entries(old_entries)
        if old_facts:
            rolling_summary = _merge_rolling_summary(
                metadata.get("rolling_summary"),
                old_facts,
            )
            if metadata.get("rolling_summary") != rolling_summary:
                metadata["rolling_summary"] = rolling_summary
                updated = True
        if len(log) > RECENT_TURN_LIMIT:
            metadata["turn_log"] = recent_entries
            updated = True
        _update_memory_cards(db, session, metadata, old_facts, recent_summary)

    if updated:
        session.metadata_json = metadata
    return updated


def _facts_from_entries(entries: Iterable[dict]) -> list[str]:
    facts = []
    for entry in entries:
        fact = _fact_line(entry)
        if fact:
            facts.append(fact)
    return facts


def _fact_line(entry: dict) -> str:
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


def _merge_rolling_summary(existing: str | None, new_facts: list[str]) -> str:
    existing_facts = existing.split(SUMMARY_SEPARATOR) if existing else []
    combined = _dedupe_facts(existing_facts + new_facts)
    return _trim_facts(combined, ROLLING_SUMMARY_LIMIT)


def _dedupe_facts(facts: Iterable[str]) -> list[str]:
    seen = set()
    ordered = []
    for fact in facts:
        if not fact or fact in seen:
            continue
        seen.add(fact)
        ordered.append(fact)
    return ordered


def _trim_facts(facts: list[str], limit: int) -> str:
    if not facts:
        return ""
    trimmed: list[str] = []
    total_len = 0
    for fact in reversed(facts):
        extra = len(fact) + (len(SUMMARY_SEPARATOR) if trimmed else 0)
        if total_len + extra > limit:
            continue
        trimmed.append(fact)
        total_len += extra
    return SUMMARY_SEPARATOR.join(reversed(trimmed))


def _update_memory_cards(
    db,
    session,
    metadata: dict,
    old_facts: list[str],
    recent_summary: list[str],
) -> None:
    location_name = metadata.get("location")
    rolling_summary = metadata.get("rolling_summary") or ""
    summary_source = rolling_summary or SUMMARY_SEPARATOR.join(recent_summary)
    summary_text = summary_source or None
    facts = _dedupe_facts(old_facts + recent_summary)

    if location_name:
        _upsert_memory_card(
            db,
            session_id=session.id,
            entity_type="location",
            entity_id=None,
            name=str(location_name),
            summary_text=summary_text,
            facts=facts,
        )

    projects = (
        db.query(Project)
        .filter(Project.session_id == session.id)
        .order_by(Project.id.asc())
        .all()
    )
    for project in projects:
        project_fact = (
            f"project={project.name} status={project.status} "
            f"progress={project.work_units_done}/{project.work_units_total}"
        )
        _upsert_memory_card(
            db,
            session_id=session.id,
            entity_type="project",
            entity_id=project.id,
            name=project.name,
            summary_text=project_fact,
            facts=_dedupe_facts([project_fact]),
        )


def _upsert_memory_card(
    db,
    *,
    session_id: int,
    entity_type: str,
    entity_id: int | None,
    name: str | None,
    summary_text: str | None,
    facts: list[str],
) -> MemoryCard:
    card = (
        db.query(MemoryCard)
        .filter(MemoryCard.session_id == session_id)
        .filter(MemoryCard.entity_type == entity_type)
        .filter(MemoryCard.entity_id == entity_id)
        .first()
    )
    if card is None:
        card = MemoryCard(
            session_id=session_id,
            entity_type=entity_type,
            entity_id=entity_id,
            name=name,
            summary_text=summary_text,
            facts_json=facts,
        )
        db.add(card)
        return card

    existing_facts = card.facts_json if isinstance(card.facts_json, list) else []
    merged_facts = _dedupe_facts(list(existing_facts) + facts)
    card.name = name or card.name
    card.summary_text = summary_text or card.summary_text
    card.facts_json = merged_facts
    return card
