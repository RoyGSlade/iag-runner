import os
from datetime import datetime
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel

from db import SessionLocal, check_db_connection
from llm.client import LLMClientError, OllamaClient
from models import (
    ArmorBase,
    ArmorVariation,
    Character,
    Clock,
    EntityLink,
    Era,
    PlayerProfile,
    Monster,
    NPC,
    Profession,
    Project,
    Race,
    Secret,
    Session as SessionModel,
    Location,
    Scene,
    Thread,
    Training,
    WeaponBase,
    WeaponVariation,
)
from rules.character import create_character_record, create_session_record, respawn_character
from rules.powers import PowerError, use_power
from rules.economy import (
    EconomyError,
    add_item_to_gear,
    is_item_legal_for_era,
    item_tags,
    quote_item_price,
    validate_credit_spend,
)
from rules.eras import (
    effective_era_profile,
    get_illegal_gear_categories,
    get_skill_aliases,
)
from rules.turn import TurnError, execute_turn


def _lookup_name(db, model, record_id: int | None) -> str | None:
    if not record_id:
        return None
    record = db.get(model, record_id)
    return record.name if record else None


CANONICAL_ERAS = {"prehistoric", "medieval", "colonial", "modern", "space"}


def _short_desc(text: str | None, limit: int = 140) -> str | None:
    if not text:
        return None
    trimmed = " ".join(text.split())
    return trimmed[:limit].strip()


def _extract_attribute_bonus(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    bonus = payload.get("attributeBonus") or payload.get("attribute_bonus")
    return bonus if isinstance(bonus, dict) else None


def _extract_traits(payload: dict | None) -> list[str] | None:
    if not isinstance(payload, dict):
        return None
    for key in ("traits", "skillChoice", "skill_choice"):
        value = payload.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    return None


def _extract_training_bonuses(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    bonuses = {}
    for key in ("armorRating", "initiative", "hitPoints", "attributeBonus"):
        if key in payload:
            bonuses[key] = payload.get(key)
    return bonuses or None


def _extract_training_majors(payload: dict | None) -> list[dict] | None:
    if not isinstance(payload, dict):
        return None
    majors = payload.get("majors")
    if not isinstance(majors, list):
        return None
    compact = []
    for major in majors:
        if not isinstance(major, dict):
            continue
        compact.append(
            {
                "name": major.get("name"),
                "skill": major.get("skill"),
                "attribute": major.get("attribute"),
            }
        )
    return compact or None


def _extract_starting_credits(payload: dict | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("startingCredits")
    if value is None:
        value = payload.get("starting_credits")
    return int(value) if isinstance(value, (int, float)) else None


def _extract_tags(profile: dict | None, patch: dict | None) -> list[str] | None:
    for source in (patch, profile):
        if isinstance(source, dict):
            value = source.get("tags")
            if isinstance(value, list):
                return [str(item) for item in value]
    return None


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

app = FastAPI(
    title="iag-runner API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/api/hello")
def hello() -> dict:
    return {"message": "Hello from iag-runner"}


@app.get("/health")
def health() -> dict:
    try:
        check_db_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok"}


class SettingCreate(BaseModel):
    type: str | None = None
    tone_tags: list[str] | None = None
    inspirations_text: str | None = None
    location_name: str | None = None


class SessionSettings(BaseModel):
    dev_mode_enabled: bool | None = None
    ooc_allowed: bool | None = None


class SessionCreate(BaseModel):
    era: str | None = None
    location: str | None = None
    seed: int | None = None
    metadata: dict[str, Any] | None = None
    setting: SettingCreate | None = None
    settings: SessionSettings | None = None


class CharacterCreate(BaseModel):
    session_id: int | None = None
    race: str | None = None
    profession: str | None = None
    training: str | None = None
    level: int | None = None
    armor: int | None = None


class PowerUseRequest(BaseModel):
    character_id: int
    power_id: str


class BuyItemRequest(BaseModel):
    character_id: int
    item_type: str
    base_name: str
    variation_name: str | None = None
    quantity: int | None = None


class TurnRequest(BaseModel):
    session_id: int
    player_text: str | None = None
    action_type: str | None = None
    payload: dict[str, Any] | None = None


class SessionImportRequest(BaseModel):
    session: dict
    character: dict | None = None


class ProjectCreateRequest(BaseModel):
    session_id: int
    character_id: int | None = None
    name: str
    type: str
    requirements: dict | None = None
    constraints: dict | None = None
    work_units_total: int
    work_units_done: int | None = None
    status: str | None = None


class ProjectAdvanceRequest(BaseModel):
    work_units: int | None = None


class MonsterCreateRequest(BaseModel):
    name: str
    role: str
    stats: dict | None = None
    abilities: dict | None = None
    weakness: dict | None = None
    tags: list[str] | None = None
    era: str | None = None


class NPCCreateRequest(BaseModel):
    session_id: int
    name: str
    role: str
    faction_id: int | None = None
    personality: dict | None = None
    goals: dict | None = None
    fears: dict | None = None
    secrets: dict | None = None
    relationships: dict | None = None
    stats: dict | None = None
    voice: dict | None = None


class LocationBootstrapRequest(BaseModel):
    name: str
    era: str | None = None
    tags: list[str] | None = None
    card: dict | None = None
    scene_description: dict | None = None
    scene_objects: dict | None = None
    scene_npcs_present: dict | None = None
    scene_exits: dict | None = None
    scene_hazards: dict | None = None


class ClockCreateRequest(BaseModel):
    session_id: int
    name: str
    steps_total: int
    steps_done: int | None = None
    deadline_time: str | None = None
    visibility: str | None = None
    trigger_tags: list[str] | None = None


class ClockAdvanceRequest(BaseModel):
    steps: int | None = None


class ThreadResolveRequest(BaseModel):
    status: str | None = None


class Session0Setting(BaseModel):
    type: str | None = None
    tone_tags: list[str] | None = None
    inspirations: list[str] | None = None


class Session0PlayerPrefs(BaseModel):
    violence_level: str | None = None
    horror_level: str | None = None
    avoid: list[str] | None = None


class Session0CompleteRequest(BaseModel):
    session_id: int
    era: str | None = None
    setting: Session0Setting | None = None
    player_prefs: Session0PlayerPrefs | None = None
    starting_hook_preference: str | None = None


class EraPreview(BaseModel):
    id: int
    name: str
    description: str | None = None
    tags: list[str] | None = None
    is_canonical: bool


class RacePreview(BaseModel):
    id: int
    name: str
    short_desc: str | None = None
    attribute_bonus: dict | None = None
    traits: list[str] | None = None


class TrainingPreview(BaseModel):
    id: int
    name: str
    short_desc: str | None = None
    bonuses: dict | None = None
    majors: list[dict] | None = None


class ProfessionPreview(BaseModel):
    id: int
    name: str
    short_desc: str | None = None
    starting_credits: int | None = None


class PlayerProfileResponse(BaseModel):
    session_id: int
    tone_prefs: dict | None = None
    themes: dict | None = None
    pacing: dict | None = None
    challenge: dict | None = None
    boundaries: dict | None = None
    interests: dict | None = None


@app.post("/sessions")
def create_session(payload: SessionCreate | None = Body(default=None)) -> dict:
    data = payload or SessionCreate()
    setting_payload = data.setting.dict() if data.setting else None
    settings_payload = data.settings.dict(exclude_none=True) if data.settings else None
    location_value = data.location
    if not setting_payload and not location_value:
        location_value = "Fallon Station"
    with SessionLocal() as db:
        session = create_session_record(
            db,
            era_name=data.era or "Space",
            location=location_value,
            seed=data.seed,
            metadata=data.metadata,
            setting=setting_payload,
            settings=settings_payload,
        )
        db.commit()
        db.refresh(session)
        return {
            "id": session.id,
            "seed": session.rng_seed,
            "metadata": session.metadata_json,
        }


@app.post("/session0/complete")
def complete_session0(payload: Session0CompleteRequest) -> dict:
    with SessionLocal() as db:
        session = db.get(SessionModel, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        setting_payload = payload.setting.model_dump() if payload.setting else {}
        prefs_payload = payload.player_prefs.model_dump() if payload.player_prefs else {}
        llm_input = {
            "era": payload.era,
            "setting": {
                "type": setting_payload.get("type"),
                "tone_tags": setting_payload.get("tone_tags") or [],
                "inspirations": setting_payload.get("inspirations") or [],
            },
            "player_prefs": {
                "violence_level": prefs_payload.get("violence_level"),
                "horror_level": prefs_payload.get("horror_level"),
                "avoid": prefs_payload.get("avoid") or [],
            },
            "starting_hook_preference": payload.starting_hook_preference,
        }

        llm_client = OllamaClient()
        try:
            setup = llm_client.complete_session0(llm_input)
        except (LLMClientError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail="Session 0 completion failed.",
            ) from exc

        metadata = dict(session.metadata_json or {})
        metadata["session_setup"] = setup.model_dump()
        metadata["era"] = setup.era
        metadata["setting"] = {
            "type": setup.setting.type,
            "tone_tags": setup.setting.tone,
            "inspirations": setup.setting.inspirations,
        }
        session.metadata_json = metadata
        db.commit()
        db.refresh(session)
        return {
            "session_id": session.id,
            "session_setup": metadata["session_setup"],
        }


@app.post("/characters")
def create_character(payload: CharacterCreate | None = Body(default=None)) -> dict:
    data = payload or CharacterCreate()
    race_name = data.race or "Android"
    profession_name = data.profession or "Bounty Hunter"
    level = data.level or 1

    with SessionLocal() as db:
        session = None
        if data.session_id:
            session = db.get(SessionModel, data.session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
        if session is None:
            session = create_session_record(
                db,
                era_name="Space",
                location="Fallon Station",
            )

        character = create_character_record(
            db,
            session=session,
            race_name=race_name,
            profession_name=profession_name,
            training_name=data.training,
            level=level,
            armor_value=data.armor,
        )
        db.commit()
        db.refresh(character)
        return {
            "id": character.id,
            "session_id": character.session_id,
            "name": character.name,
            "race_id": character.race_id,
            "profession_id": character.profession_id,
            "training_id": character.training_id,
            "level": character.level,
            "attributes": character.attributes_json,
            "gear_pack": character.gear_pack_json,
            "statuses": character.statuses_json,
        }


@app.post("/use_power")
def use_power_endpoint(payload: PowerUseRequest) -> dict:
    with SessionLocal() as db:
        character = db.get(Character, payload.character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="Character not found")
        if character.session_id is None:
            raise HTTPException(status_code=400, detail="Character has no session")
        session = db.get(SessionModel, character.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        era_name = ""
        if isinstance(session.metadata_json, dict):
            era_name = session.metadata_json.get("era", "")

        try:
            result = use_power(era_name, character, payload.power_id)
        except PowerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        db.commit()
        db.refresh(character)
        power = result.power
        return {
            "character_id": character.id,
            "power_id": power.power_id,
            "school": power.school,
            "activation_cost": power.activation_cost,
            "duration": power.duration,
            "range": power.range,
            "uses": power.uses,
            "effect": result.effect,
            "statuses": character.statuses_json,
            "attributes": character.attributes_json,
        }


@app.post("/buy_item")
def buy_item_endpoint(payload: BuyItemRequest) -> dict:
    item_type = payload.item_type.strip().lower()
    if item_type not in {"weapon", "armor"}:
        raise HTTPException(status_code=400, detail="Unsupported item type")

    quantity = payload.quantity or 1
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    with SessionLocal() as db:
        character = db.get(Character, payload.character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="Character not found")
        if character.session_id is None:
            raise HTTPException(status_code=400, detail="Character has no session")
        session = db.get(SessionModel, character.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        era_name = ""
        if isinstance(session.metadata_json, dict):
            era_name = session.metadata_json.get("era", "")
        era = None
        if era_name:
            era = (
                db.query(Era)
                .filter(Era.name.ilike(era_name))
                .first()
            )

        base = None
        variation = None
        if item_type == "weapon":
            base = (
                db.query(WeaponBase)
                .filter(WeaponBase.name.ilike(payload.base_name))
                .first()
            )
            if base and payload.variation_name:
                variation = (
                    db.query(WeaponVariation)
                    .filter(WeaponVariation.base_id == base.id)
                    .filter(WeaponVariation.name.ilike(payload.variation_name))
                    .first()
                )
        else:
            base = (
                db.query(ArmorBase)
                .filter(ArmorBase.name.ilike(payload.base_name))
                .first()
            )
            if base and payload.variation_name:
                variation = (
                    db.query(ArmorVariation)
                    .filter(ArmorVariation.base_id == base.id)
                    .filter(ArmorVariation.name.ilike(payload.variation_name))
                    .first()
                )

        if base is None:
            raise HTTPException(status_code=404, detail="Base item not found")

        tags = item_tags(base, variation)
        if not is_item_legal_for_era(
            era_name,
            base.name,
            tags,
            era.profile_json if era else None,
            era.patch_json if era else None,
        ):
            raise HTTPException(status_code=400, detail="Item not allowed in this era")

        quote = quote_item_price(base, variation)
        total_cost = quote.total_price * quantity
        try:
            gear_pack = validate_credit_spend(character.gear_pack_json, total_cost)
        except EconomyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        item_entry = {
            "type": item_type,
            "base": base.name,
            "variation": variation.name if variation else None,
            "quantity": quantity,
            "unit_cost": quote.total_price,
            "total_cost": total_cost,
        }
        gear_pack = add_item_to_gear(gear_pack, item_entry)
        character.gear_pack_json = gear_pack
        db.commit()
        db.refresh(character)

        return {
            "character_id": character.id,
            "item": item_entry,
            "credits": character.gear_pack_json.get("credits", 0),
        }


@app.get("/era/{era_name}/profile")
def get_era_profile(era_name: str) -> dict:
    with SessionLocal() as db:
        era = db.query(Era).filter(Era.name.ilike(era_name)).first()
        if era is None:
            raise HTTPException(status_code=404, detail="Era not found")
        effective = effective_era_profile(era)
        return {
            "era": era.name,
            "profile": era.profile_json,
            "patch": era.patch_json,
            "effective": effective,
            "skill_aliases": get_skill_aliases(era),
            "illegal_gear_categories": sorted(get_illegal_gear_categories(era)),
        }


@app.post("/characters/{character_id}/respawn")
def respawn(character_id: int) -> dict:
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="Character not found")
        if character.session_id is None:
            raise HTTPException(status_code=400, detail="Character has no session")
        session = db.get(SessionModel, character.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        era_name = ""
        if isinstance(session.metadata_json, dict):
            era_name = session.metadata_json.get("era", "")
        if era_name.strip().lower() != "space":
            raise HTTPException(status_code=400, detail="Respawn not allowed outside Space")

        character = respawn_character(character)
        db.commit()
        db.refresh(character)
        return {
            "character": {
                "id": character.id,
                "session_id": character.session_id,
                "name": character.name,
                "attributes_json": character.attributes_json,
                "statuses_json": character.statuses_json,
                "gear_pack_json": character.gear_pack_json,
            }
        }


@app.post("/sessions/{session_id}/restart")
def restart_session(session_id: int) -> dict:
    with SessionLocal() as db:
        session = db.get(SessionModel, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        character = (
            db.query(Character).filter(Character.session_id == session_id).first()
        )
        era_name = "Space"
        location = "Fallon Station"
        setting_payload = None
        settings_payload = None
        if isinstance(session.metadata_json, dict):
            era_name = session.metadata_json.get("era", era_name)
            location = session.metadata_json.get("location", location)
            setting_value = session.metadata_json.get("setting")
            if isinstance(setting_value, dict):
                setting_payload = dict(setting_value)
            settings_value = session.metadata_json.get("settings")
            if isinstance(settings_value, dict):
                settings_payload = dict(settings_value)

        new_session = create_session_record(
            db,
            era_name=era_name,
            location=location,
            setting=setting_payload,
            settings=settings_payload,
        )
        race_name = None
        profession_name = None
        training_name = None
        level = 1
        if character:
            race_name = _lookup_name(db, Race, character.race_id)
            profession_name = _lookup_name(db, Profession, character.profession_id)
            training_name = _lookup_name(db, Training, character.training_id)
            level = character.level or level

        new_character = create_character_record(
            db,
            session=new_session,
            race_name=race_name or "Android",
            profession_name=profession_name or "Bounty Hunter",
            training_name=training_name,
            level=level,
        )
        db.commit()
        db.refresh(new_session)
        db.refresh(new_character)
        return {
            "session": {
                "id": new_session.id,
                "seed": new_session.rng_seed,
                "metadata": new_session.metadata_json,
            },
            "character": {
                "id": new_character.id,
                "session_id": new_character.session_id,
                "name": new_character.name,
                "race_id": new_character.race_id,
                "profession_id": new_character.profession_id,
                "training_id": new_character.training_id,
                "level": new_character.level,
                "attributes": new_character.attributes_json,
                "gear_pack": new_character.gear_pack_json,
                "statuses": new_character.statuses_json,
            },
        }


@app.post("/sessions/{session_id}/export")
def export_session(session_id: int) -> dict:
    with SessionLocal() as db:
        session = db.get(SessionModel, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        character = (
            db.query(Character).filter(Character.session_id == session_id).first()
        )
        if character is None:
            raise HTTPException(status_code=404, detail="Character not found")
        return {
            "session": {
                "id": session.id,
                "rng_seed": session.rng_seed,
                "metadata_json": session.metadata_json,
            },
            "character": {
                "id": character.id,
                "session_id": character.session_id,
                "name": character.name,
                "race_id": character.race_id,
                "profession_id": character.profession_id,
                "training_id": character.training_id,
                "level": character.level,
                "attributes_json": character.attributes_json,
                "skill_levels_json": character.skill_levels_json,
                "gear_pack_json": character.gear_pack_json,
                "statuses_json": character.statuses_json,
            },
        }


@app.post("/sessions/import")
def import_session(payload: SessionImportRequest) -> dict:
    with SessionLocal() as db:
        session_data = payload.session or {}
        metadata = session_data.get("metadata_json")
        session = SessionModel(
            rng_seed=session_data.get("rng_seed"),
            metadata_json=metadata if isinstance(metadata, dict) else {},
        )
        db.add(session)
        db.flush()

        character_payload = payload.character or {}
        character = Character(
            session_id=session.id,
            name=character_payload.get("name") or "Imported Character",
            race_id=character_payload.get("race_id"),
            profession_id=character_payload.get("profession_id"),
            training_id=character_payload.get("training_id"),
            level=character_payload.get("level"),
            attributes_json=character_payload.get("attributes_json") or {},
            skill_levels_json=character_payload.get("skill_levels_json"),
            gear_pack_json=character_payload.get("gear_pack_json") or {},
            statuses_json=character_payload.get("statuses_json") or {},
        )
        db.add(character)
        db.commit()
        db.refresh(session)
        db.refresh(character)

        return {
            "session": {
                "id": session.id,
                "rng_seed": session.rng_seed,
                "metadata_json": session.metadata_json,
            },
            "character": {
                "id": character.id,
                "session_id": character.session_id,
                "name": character.name,
                "race_id": character.race_id,
                "profession_id": character.profession_id,
                "training_id": character.training_id,
                "level": character.level,
                "attributes_json": character.attributes_json,
                "skill_levels_json": character.skill_levels_json,
                "gear_pack_json": character.gear_pack_json,
                "statuses_json": character.statuses_json,
            },
        }


@app.get("/eras", response_model=list[EraPreview])
def list_eras() -> list[EraPreview]:
    with SessionLocal() as db:
        records = db.query(Era).order_by(Era.name.asc()).all()
        return [
            EraPreview(
                id=record.id,
                name=record.name,
                description=record.description,
                tags=_extract_tags(record.profile_json, record.patch_json),
                is_canonical=record.name.lower() in CANONICAL_ERAS,
            )
            for record in records
        ]


@app.get("/races", response_model=list[RacePreview])
def list_races() -> list[RacePreview]:
    with SessionLocal() as db:
        records = db.query(Race).order_by(Race.name.asc()).all()
        return [
            RacePreview(
                id=record.id,
                name=record.name,
                short_desc=_short_desc(record.description),
                attribute_bonus=_extract_attribute_bonus(record.attributes_json),
                traits=_extract_traits(record.attributes_json),
            )
            for record in records
        ]


@app.get("/trainings", response_model=list[TrainingPreview])
def list_trainings() -> list[TrainingPreview]:
    with SessionLocal() as db:
        records = db.query(Training).order_by(Training.name.asc()).all()
        return [
            TrainingPreview(
                id=record.id,
                name=record.name,
                short_desc=_short_desc(record.description),
                bonuses=_extract_training_bonuses(record.skill_levels_json),
                majors=_extract_training_majors(record.skill_levels_json),
            )
            for record in records
        ]


@app.get("/professions", response_model=list[ProfessionPreview])
def list_professions() -> list[ProfessionPreview]:
    with SessionLocal() as db:
        records = db.query(Profession).order_by(Profession.name.asc()).all()
        return [
            ProfessionPreview(
                id=record.id,
                name=record.name,
                short_desc=_short_desc(record.description),
                starting_credits=_extract_starting_credits(record.attributes_json),
            )
            for record in records
        ]


@app.post("/resolve_turn")
def resolve_turn(payload: TurnRequest) -> dict:
    try:
        result = execute_turn(
            payload.session_id,
            payload.player_text,
            action_type=payload.action_type,
            payload=payload.payload,
        )
    except TurnError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = {
        "intent": result.intent,
        "rolls": result.rolls,
        "outcome": result.outcome,
        "state_diff": result.state_diff,
        "narration_prompt_context": result.narration_prompt_context,
        "narration": result.narration,
        "suggested_actions": result.suggested_actions,
        "needs_clarification": result.needs_clarification,
        "clarification_question": result.clarification_question,
        "clarification_questions": result.clarification_questions,
        "project_created": result.project_created,
    }
    if os.getenv("DEV_MODE", "").lower() == "true":
        response["raw_llm_output"] = result.raw_llm_output
        response["parsed_intent"] = result.parsed_intent
        response["validation_errors"] = result.validation_errors
    return response


@app.post("/projects")
def create_project(payload: ProjectCreateRequest) -> dict:
    if payload.work_units_total <= 0:
        raise HTTPException(status_code=400, detail="work_units_total must be positive")
    with SessionLocal() as db:
        session = db.get(SessionModel, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if payload.character_id:
            character = db.get(Character, payload.character_id)
            if character is None:
                raise HTTPException(status_code=404, detail="Character not found")
        done_units = payload.work_units_done or 0
        status = payload.status or "active"
        if done_units >= payload.work_units_total:
            status = "completed"
        project = Project(
            session_id=payload.session_id,
            character_id=payload.character_id,
            name=payload.name,
            type=payload.type,
            requirements_json=payload.requirements,
            constraints_json=payload.constraints,
            work_units_total=payload.work_units_total,
            work_units_done=done_units,
            status=status,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
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


@app.post("/projects/{project_id}/advance")
def advance_project(project_id: int, payload: ProjectAdvanceRequest) -> dict:
    units = payload.work_units or 1
    if units <= 0:
        raise HTTPException(status_code=400, detail="work_units must be positive")
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.status in {"completed", "failed"}:
            raise HTTPException(status_code=400, detail="Project is not active")
        project.work_units_done += units
        if project.work_units_done >= project.work_units_total:
            project.status = "completed"
        db.commit()
        db.refresh(project)
        return {
            "id": project.id,
            "work_units_total": project.work_units_total,
            "work_units_done": project.work_units_done,
            "status": project.status,
        }


@app.get("/sessions/{session_id}/projects")
def list_projects(session_id: int) -> list[dict]:
    with SessionLocal() as db:
        records = (
            db.query(Project)
            .filter(Project.session_id == session_id)
            .order_by(Project.id.asc())
            .all()
        )
        return [
            {
                "id": record.id,
                "session_id": record.session_id,
                "character_id": record.character_id,
                "name": record.name,
                "type": record.type,
                "requirements": record.requirements_json,
                "constraints": record.constraints_json,
                "work_units_total": record.work_units_total,
                "work_units_done": record.work_units_done,
                "status": record.status,
            }
            for record in records
        ]


@app.post("/content/monster")
def create_monster(payload: MonsterCreateRequest) -> dict:
    role = payload.role.strip().lower()
    if role not in {"brute", "ambush", "controller", "horror"}:
        raise HTTPException(status_code=400, detail="Unsupported monster role")

    stats = payload.stats or {}
    if not isinstance(stats, dict):
        raise HTTPException(status_code=400, detail="stats must be an object")
    stats.setdefault("hp", 6)
    stats.setdefault("ar", 10)
    stats.setdefault("attacks", [{"name": "Strike", "damage": "1d6"}])

    abilities = payload.abilities or {}
    weakness = payload.weakness or {}
    tags = payload.tags or []

    with SessionLocal() as db:
        monster = Monster(
            name=payload.name,
            role=role,
            stats_json=stats,
            abilities_json=abilities,
            weakness_json=weakness,
            tags_json={"tags": tags},
            era=payload.era,
        )
        db.add(monster)
        db.commit()
        db.refresh(monster)
        return {
            "id": monster.id,
            "name": monster.name,
            "role": monster.role,
            "stats": monster.stats_json,
            "abilities": monster.abilities_json,
            "weakness": monster.weakness_json,
            "tags": monster.tags_json.get("tags", []),
            "era": monster.era,
        }


@app.post("/content/npc")
def create_npc(payload: NPCCreateRequest) -> dict:
    with SessionLocal() as db:
        session = db.get(SessionModel, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        npc = NPC(
            session_id=payload.session_id,
            name=payload.name,
            role=payload.role,
            faction_id=payload.faction_id,
            personality_json=payload.personality or {},
            goals_json=payload.goals or {},
            fears_json=payload.fears or {},
            secrets_json=payload.secrets or {},
            relationships_json=payload.relationships or {},
            stats_json=payload.stats or {},
            voice_json=payload.voice or {},
        )
        db.add(npc)
        db.commit()
        db.refresh(npc)
        return {
            "id": npc.id,
            "session_id": npc.session_id,
            "name": npc.name,
            "role": npc.role,
            "faction_id": npc.faction_id,
            "personality": npc.personality_json,
            "goals": npc.goals_json,
            "fears": npc.fears_json,
            "secrets": npc.secrets_json,
            "relationships": npc.relationships_json,
            "stats": npc.stats_json,
            "voice": npc.voice_json,
        }


@app.get("/sessions/{session_id}/npcs")
def list_npcs(session_id: int) -> list[dict]:
    with SessionLocal() as db:
        records = (
            db.query(NPC)
            .filter(NPC.session_id == session_id)
            .order_by(NPC.id.asc())
            .all()
        )
        return [
            {
                "id": record.id,
                "session_id": record.session_id,
                "name": record.name,
                "role": record.role,
                "faction_id": record.faction_id,
                "personality": record.personality_json,
                "goals": record.goals_json,
                "fears": record.fears_json,
                "secrets": record.secrets_json,
                "relationships": record.relationships_json,
                "stats": record.stats_json,
                "voice": record.voice_json,
            }
            for record in records
        ]


@app.post("/content/location_bootstrap")
def create_location_bootstrap(payload: LocationBootstrapRequest) -> dict:
    card = payload.card or {}
    card.setdefault("authority", "unknown")
    card.setdefault("economy", "unknown")
    card.setdefault("danger", "unknown")
    card.setdefault("secret", "unknown")
    card.setdefault("hooks", [])

    with SessionLocal() as db:
        location = Location(
            name=payload.name,
            era=payload.era,
            tags_json={"tags": payload.tags or []},
            card_json=card,
        )
        db.add(location)
        db.flush()

        scene = Scene(
            location_id=location.id,
            description_json=payload.scene_description or {},
            objects_json=payload.scene_objects or {},
            npcs_present_json=payload.scene_npcs_present or {},
            exits_json=payload.scene_exits or {},
            hazards_json=payload.scene_hazards or {},
        )
        db.add(scene)
        db.commit()
        db.refresh(location)
        db.refresh(scene)
        return {
            "location": {
                "id": location.id,
                "name": location.name,
                "era": location.era,
                "tags": location.tags_json.get("tags", []),
                "card": location.card_json,
            },
            "scene": {
                "id": scene.id,
                "location_id": scene.location_id,
                "description": scene.description_json,
                "objects": scene.objects_json,
                "npcs_present": scene.npcs_present_json,
                "exits": scene.exits_json,
                "hazards": scene.hazards_json,
            },
        }


@app.post("/clocks")
def create_clock(payload: ClockCreateRequest) -> dict:
    if payload.steps_total <= 0:
        raise HTTPException(status_code=400, detail="steps_total must be positive")
    visibility = (payload.visibility or "gm").lower()
    if visibility not in {"player", "gm"}:
        raise HTTPException(status_code=400, detail="visibility must be player or gm")
    with SessionLocal() as db:
        session = db.get(SessionModel, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        steps_done = payload.steps_done or 0
        clock = Clock(
            session_id=payload.session_id,
            name=payload.name,
            steps_total=payload.steps_total,
            steps_done=steps_done,
            deadline_time=_parse_deadline(payload.deadline_time),
            visibility=visibility,
            trigger_tags_json={"tags": payload.trigger_tags or []},
        )
        db.add(clock)
        db.commit()
        db.refresh(clock)
        return _clock_payload(clock)


@app.post("/clocks/{clock_id}/advance")
def advance_clock(clock_id: int, payload: ClockAdvanceRequest) -> dict:
    steps = payload.steps or 1
    if steps <= 0:
        raise HTTPException(status_code=400, detail="steps must be positive")
    with SessionLocal() as db:
        clock = db.get(Clock, clock_id)
        if clock is None:
            raise HTTPException(status_code=404, detail="Clock not found")
        clock.steps_done += steps
        if clock.steps_done > clock.steps_total:
            clock.steps_done = clock.steps_total
        db.commit()
        db.refresh(clock)
        return _clock_payload(clock)


@app.get("/sessions/{session_id}/clocks")
def list_clocks(session_id: int) -> list[dict]:
    with SessionLocal() as db:
        records = (
            db.query(Clock)
            .filter(Clock.session_id == session_id)
            .order_by(Clock.id.asc())
            .all()
        )
        return [_clock_payload(record) for record in records]


@app.get("/sessions/{session_id}/profile", response_model=PlayerProfileResponse)
def get_player_profile(session_id: int) -> PlayerProfileResponse:
    with SessionLocal() as db:
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
            db.commit()
            db.refresh(profile)
        return PlayerProfileResponse(
            session_id=profile.session_id or session_id,
            tone_prefs=profile.tone_prefs_json,
            themes=profile.themes_json,
            pacing=profile.pacing_json,
            challenge=profile.challenge_json,
            boundaries=profile.boundaries_json,
            interests=profile.interests_json,
        )


@app.get("/sessions/{session_id}/threads")
def list_threads(session_id: int) -> list[dict]:
    with SessionLocal() as db:
        records = (
            db.query(Thread)
            .filter(Thread.session_id == session_id)
            .order_by(Thread.id.asc())
            .all()
        )
        return [_thread_payload(record) for record in records]


@app.post("/threads/{thread_id}/resolve")
def resolve_thread(thread_id: int, payload: ThreadResolveRequest) -> dict:
    status = payload.status or "resolved"
    if status not in {"resolved", "ignored", "open"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    with SessionLocal() as db:
        thread = db.get(Thread, thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread.status = status
        db.commit()
        db.refresh(thread)
        return _thread_payload(thread)


def _clock_payload(clock: Clock) -> dict:
    return {
        "id": clock.id,
        "session_id": clock.session_id,
        "name": clock.name,
        "steps_total": clock.steps_total,
        "steps_done": clock.steps_done,
        "deadline_time": clock.deadline_time.isoformat() if clock.deadline_time else None,
        "visibility": clock.visibility,
        "trigger_tags": (clock.trigger_tags_json or {}).get("tags", []),
    }


def _thread_payload(thread: Thread) -> dict:
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


def _parse_deadline(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="deadline_time must be ISO format")


@app.get("/graph/entity/{entity_type}/{entity_id}")
def get_entity_graph(entity_type: str, entity_id: int) -> dict:
    with SessionLocal() as db:
        outgoing = (
            db.query(EntityLink)
            .filter(EntityLink.from_type == entity_type)
            .filter(EntityLink.from_id == entity_id)
            .order_by(EntityLink.id.asc())
            .all()
        )
        incoming = (
            db.query(EntityLink)
            .filter(EntityLink.to_type == entity_type)
            .filter(EntityLink.to_id == entity_id)
            .order_by(EntityLink.id.asc())
            .all()
        )
        secrets = (
            db.query(Secret)
            .filter(Secret.owner_type == entity_type)
            .filter(Secret.owner_id == entity_id)
            .order_by(Secret.id.asc())
            .all()
        )

        return {
            "entity": {"type": entity_type, "id": entity_id},
            "outgoing": [
                {
                    "from_type": link.from_type,
                    "from_id": link.from_id,
                    "to_type": link.to_type,
                    "to_id": link.to_id,
                    "relation": link.relation,
                    "secrecy_level": link.secrecy_level,
                }
                for link in outgoing
            ],
            "incoming": [
                {
                    "from_type": link.from_type,
                    "from_id": link.from_id,
                    "to_type": link.to_type,
                    "to_id": link.to_id,
                    "relation": link.relation,
                    "secrecy_level": link.secrecy_level,
                }
                for link in incoming
            ],
            "secrets": [
                {
                    "owner_type": secret.owner_type,
                    "owner_id": secret.owner_id,
                    "secret_text": secret.secret_text,
                    "linked_entities": secret.linked_entities_json,
                }
                for secret in secrets
            ],
        }
