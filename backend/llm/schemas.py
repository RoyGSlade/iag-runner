from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel


class TargetRef(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: int | None = None
    name: str | None = None
    type: str | None = None


class Movement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["walk", "run", "dash", "teleport", "none"] = "none"
    distance: int | None = None
    destination: str | None = None


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action_type: Literal[
        "explore",
        "scene_request",
        "interact",
        "attack",
        "use_power",
        "buy_item",
        "move",
        "ask_gm",
        "ask_clarifying_question",
        "invalid",
        "other",
    ]
    targets: list[TargetRef] = Field(default_factory=list)
    skill_used: str | None = None
    power_used: str | None = None
    item_used: str | None = None
    movement: Movement | None = None
    dialogue: str | None = None
    reason: str | None = None
    metadata: dict[str, JsonValue] | None = None
    confidence: float | int | None = Field(default=None, ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list)


class NarrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    state_summary: dict[str, JsonValue]
    outcome: dict[str, JsonValue]
    tone: str | None = None
    style: str | None = None


class LLMError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str
    message: str
    details: dict[str, JsonValue] | None = None


class SessionSetupSetting(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: str
    tone: list[str]
    inspirations: list[str]


class SessionSetupPlayerPrefs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    violence_level: str
    horror: str
    avoid: list[str]


class SessionSetupStartingSituation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    hook: str
    first_scene: str
    immediate_problem: str
    npcs: list[str]


class SessionSetup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    era: str
    setting: SessionSetupSetting
    player_prefs: SessionSetupPlayerPrefs
    starting_situation: SessionSetupStartingSituation


class TurnEnvelopeClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    primary_category: str
    secondary_category: str | None = None


class TurnEnvelopePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str | None = None
    steps: list[str] | None = None


class TurnEnvelopeCouncil(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    planner_notes: str | None = None
    validator_notes: str | None = None
    lorekeeper_notes: str | None = None
    director_notes: str | None = None
    speaker_outline: str | None = None


class ContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["npc", "monster", "item", "location", "system", "book"]
    purpose: Literal["challenge", "reward", "scare", "tension", "relax", "plot", "flavor"]
    era: str | None = None
    tags: list[str] | None = None
    difficulty: str | None = None
    constraints: dict[str, JsonValue]
    reason: str


class GMPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal[
        "move",
        "attack",
        "interact",
        "investigate",
        "social",
        "use_power",
        "craft",
        "improvise",
        "downtime",
    ]
    actor_id: int
    targets: list[str]
    skill_used: str | None = None
    power_used: str | None = None
    time_cost: Literal["none", "action", "reaction", "minutes", "hours", "days"]
    risk_level: Literal["low", "med", "high"]
    notes: str
    complexity: int | None = None


class GMPlan(RootModel[list[GMPlanStep]]):
    model_config = ConfigDict(strict=True)


class TurnEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["gm", "ooc", "dev"]
    protocol_id: str
    confidence: Literal["high", "medium", "low"]
    classification: TurnEnvelopeClassification
    ooc_questions: list[str] = Field(default_factory=list, max_length=3)
    gm_plan: GMPlan | None = None
    content_requests: list[ContentRequest] | None = None
    memory_suggestions: dict[str, JsonValue] | None = None
    dev_report: dict[str, JsonValue] | None = None
    council: TurnEnvelopeCouncil | None = None
